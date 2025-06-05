import json
import xml.etree.ElementTree as ET
import requests
from typing import Dict, List, Optional, Any
import os
import logging
from twilio.rest import Client
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import tempfile
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import httpx
from datetime import datetime
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import play
    ELEVENLABS_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("ElevenLabs not available. Voice features will be disabled.")
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None
    play = None
from .restaurant_data_aggregator_module import get_openai_client  # Import from the correct module

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
UPCRAFTAI_API_KEY = os.getenv("UPCRAFTAI_API_KEY")
CUSTOMERIO_API_KEY = os.getenv("CUSTOMERIO_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# AWS S3 Configuration for audio hosting
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Initialize ElevenLabs client
elevenlabs_client = None
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY:
    try:
        elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        logger.info("ElevenLabs client successfully initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize ElevenLabs client: {str(e)}")
        elevenlabs_client = None
else:
    elevenlabs_client = None

# Initialize Twilio client
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {str(e)}")

# Initialize S3 client with proper error handling
s3_client = None
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and S3_BUCKET_NAME:
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        logger.info("S3 client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {str(e)}")
else:
    missing_vars = []
    if not AWS_ACCESS_KEY_ID:
        missing_vars.append("AWS_ACCESS_KEY_ID")
    if not AWS_SECRET_ACCESS_KEY:
        missing_vars.append("AWS_SECRET_ACCESS_KEY")
    if not S3_BUCKET_NAME:
        missing_vars.append("S3_BUCKET_NAME")
    logger.warning(f"S3 not configured - missing: {', '.join(missing_vars)}")

def parse_xml_analysis(xml_content: str) -> Dict:
    """Parse XML analysis content and extract key insights."""
    try:
        root = ET.fromstring(xml_content)
        
        competitive_landscape = [item.text for item in root.find("competitive_landscape").findall("item")]
        opportunity_gaps = [item.text for item in root.find("opportunity_gaps").findall("item")]
        prioritized_actions = [
            {
                "action": item.find("action").text,
                "impact": item.find("impact").text,
                "feasibility": item.find("feasibility").text,
                "rationale": item.find("rationale").text
            } for item in root.find("prioritized_actions").findall("action_item")
        ]
        
        return {
            "competitive_landscape": competitive_landscape,
            "opportunity_gaps": opportunity_gaps,
            "prioritized_actions": prioritized_actions
        }
    except Exception as e:
        logger.error(f"XML parsing error: {str(e)}")
        return {"error": f"XML parsing error: {str(e)}"}

async def generate_sms_content(analysis: Dict, restaurant_name: str) -> str:
    """Generate personalized SMS content using UpcraftAI."""
    try:
        top_action = analysis["prioritized_actions"][0]["action"] if analysis["prioritized_actions"] else "optimize your menu pricing"
        prompt = f"""
        Craft a concise, engaging SMS for {restaurant_name}, a restaurant owner who prefers texting. Highlight one actionable insight: '{top_action}'. Keep it under 160 characters, friendly, and low-tech.
        """
        
        headers = {
            "Authorization": f"Bearer {UPCRAFTAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "max_length": 160,
            "temperature": 0.7
        }
        
        response = requests.post("https://api.upcraft.ai/v1/sms/generate", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()["text"]
        logger.info(f"Generated SMS content for {restaurant_name}: {len(result)} characters")
        return result
        
    except Exception as e:
        logger.error(f"SMS content generation failed for {restaurant_name}: {str(e)}")
        # Fallback SMS content
        return f"Hi {restaurant_name}! We found some great opportunities to boost your restaurant's success. Reply for a free consultation!"

async def send_sms(phone: str, content: str):
    """Send SMS via UpcraftAI."""
    try:
        headers = {
            "Authorization": f"Bearer {UPCRAFTAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "to": phone,
            "message": content
        }
        
        response = requests.post("https://api.upcraft.ai/v1/sms/send", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"SMS sent successfully to {phone}")
        return result
        
    except Exception as e:
        logger.error(f"SMS sending failed to {phone}: {str(e)}")
        raise

async def generate_email_content(analysis: Dict, restaurant_name: str) -> Dict:
    """Generate personalized email content using Customer.io."""
    try:
        actions = [action["action"] for action in analysis["prioritized_actions"][:3]]
        prompt = f"""
        Create a concise email for {restaurant_name}, a restaurant owner. Summarize 3 growth strategies: {', '.join(actions)}. Keep it professional, under 200 words, with a call-to-action to reply for a free consultation. Include subject line.
        """
        
        headers = {
            "Authorization": f"Bearer {CUSTOMERIO_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt,
            "max_length": 200,
            "template": "restaurant_growth"
        }
        
        response = requests.post("https://api.customer.io/v1/email/generate", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Generated email content for {restaurant_name}")
        return result
        
    except Exception as e:
        logger.error(f"Email content generation failed for {restaurant_name}: {str(e)}")
        # Fallback email content
        return {
            "subject": f"Growth Opportunities for {restaurant_name}",
            "body": f"Hi there!\n\nWe've analyzed {restaurant_name} and found some exciting opportunities to boost your business. We'd love to share our insights with you.\n\nReply to this email for a free consultation!\n\nBest regards,\nAI Restaurant Consulting Team"
        }

async def send_email(email: str, content: Dict):
    """Send email via Customer.io."""
    try:
        headers = {
            "Authorization": f"Bearer {CUSTOMERIO_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "to": email,
            "subject": content["subject"],
            "body": content["body"],
            "campaign_id": "restaurant_outreach"
        }
        
        response = requests.post("https://api.customer.io/v1/email/send", headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Email sent successfully to {email}")
        return result
        
    except Exception as e:
        logger.error(f"Email sending failed to {email}: {str(e)}")
        raise

async def generate_voice_message(restaurant_name: str, analysis_data: Dict) -> str:
    """Generate voice message using ElevenLabs for phone outreach."""
    if not elevenlabs_client:
        logger.warning(f"Voice message generation skipped for {restaurant_name} - ElevenLabs not configured")
        return None
    
    try:
        # Generate script for voice message
        top_actions = analysis_data.get("prioritized_actions", [])[:2]  # Get top 2 actions
        action_text = ""
        if top_actions:
            actions_list = [action.get("action", "") for action in top_actions]
            action_text = f"We found opportunities in {' and '.join(actions_list)}"
        else:
            action_text = "We found several growth opportunities for your restaurant"
        
        voice_script = f"""
        Hi, this is a message for {restaurant_name}. 
        
        We recently analyzed your restaurant and {action_text}. 
        
        We'd love to share our insights with you in a free consultation. 
        
        Please call us back or visit our website to schedule a time that works for you.
        
        Thank you and have a great day!
        """
        
        logger.info(f"Generating voice message for {restaurant_name} using ElevenLabs")
        
        # Generate audio using ElevenLabs with the new API
        audio_response = elevenlabs_client.generate(
            text=voice_script.strip(),
            voice="Rachel",  # Popular female voice
            model="eleven_monolingual_v1"
        )
        
        # Save audio to temporary file
        temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        
        # Write audio data to file - the response is now bytes
        if hasattr(audio_response, '__iter__'):
            # If it's iterable chunks
            for chunk in audio_response:
                temp_audio_file.write(chunk)
        else:
            # If it's direct bytes
            temp_audio_file.write(audio_response)
        
        temp_audio_file.close()
        
        logger.info(f"Voice message generated successfully for {restaurant_name}, saved to {temp_audio_file.name}")
        return temp_audio_file.name
        
    except Exception as e:
        logger.error(f"Voice message generation failed for {restaurant_name}: {str(e)}")
        return None

async def upload_audio_to_s3(file_path: str, bucket_name: str = None, object_name: str = None) -> str:
    """Upload an audio file to S3 bucket and return its public URL."""
    if not s3_client:
        logger.error("S3 client not configured - cannot upload audio file")
        return None
    
    if not bucket_name:
        bucket_name = S3_BUCKET_NAME
    
    if not object_name:
        # Generate unique object name
        file_extension = os.path.splitext(file_path)[1]
        object_name = f"voice-messages/{uuid.uuid4()}{file_extension}"
    
    try:
        logger.info(f"Uploading audio file to S3: {file_path} -> s3://{bucket_name}/{object_name}")
        
        # Upload file to S3
        s3_client.upload_file(
            file_path, 
            bucket_name, 
            object_name,
            ExtraArgs={
                'ContentType': 'audio/mpeg',
                'ACL': 'public-read'  # Make file publicly accessible
            }
        )
        
        # Generate public URL
        public_url = f"https://{bucket_name}.s3.{AWS_REGION}.amazonaws.com/{object_name}"
        
        logger.info(f"Audio file uploaded successfully to S3: {public_url}")
        
        # Clean up temporary file
        try:
            os.unlink(file_path)
            logger.debug(f"Temporary file cleaned up: {file_path}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temporary file {file_path}: {cleanup_error}")
        
        return public_url
        
    except (NoCredentialsError, PartialCredentialsError) as cred_error:
        logger.error(f"AWS credentials error during S3 upload: {str(cred_error)}")
        return None
    except ClientError as client_error:
        logger.error(f"AWS S3 client error during upload: {str(client_error)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during S3 upload: {str(e)}")
        return None

async def make_voice_call(phone_number: str, audio_url: str, restaurant_name: str) -> bool:
    """Make voice call using Twilio with the provided audio URL."""
    if not twilio_client:
        logger.warning(f"Voice calling skipped for {phone_number} ({restaurant_name}) - Twilio not configured")
        return False
    
    if not TWILIO_PHONE_NUMBER:
        logger.error("TWILIO_PHONE_NUMBER not configured - cannot make voice calls")
        return False
    
    try:
        logger.info(f"Initiating voice call to {phone_number} for {restaurant_name}")
        
        # Create TwiML for playing the audio
        twiml_url = f"https://handler.twilio.com/twiml/EH{uuid.uuid4().hex[:20]}"  # Generate unique TwiML URL
        
        # For now, use a simple Play verb - in production you'd want to host your own TwiML
        call = twilio_client.calls.create(
            url=f"http://twimlets.com/holdmusic?Bucket={audio_url}",  # Simple TwiML that plays URL
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER
        )
        
        call_sid = call.sid
        logger.info(f"Voice call initiated successfully to {phone_number} for {restaurant_name}: {call_sid}")
        return call_sid
        
    except Exception as e:
        logger.error(f"Voice call failed to {phone_number} for {restaurant_name}: {str(e)}")
        return False

async def send_outreach_to_target(report_data: Dict, target_analysis_xml: str):
    """Sends outreach to the target restaurant with enhanced voice capabilities."""
    logger.info(f"Starting outreach to target restaurant: {report_data['restaurant_name']}")
    
    target_analysis = parse_xml_analysis(target_analysis_xml)
    if "error" in target_analysis:
        logger.error(f"Failed to parse target analysis XML: {target_analysis['error']}")
        return
    
    target_name = report_data["restaurant_name"]
    target_email = report_data.get("email")
    target_phone = report_data["website_data"]["contact"].get("phone")
    
    # Send SMS if phone number available
    if target_phone:
        try:
            sms_content = await generate_sms_content(target_analysis, target_name)
            await send_sms(target_phone, sms_content)
            logger.info(f"SMS sent successfully to {target_name}")
        except Exception as sms_error:
            logger.error(f"SMS sending failed for {target_name}: {str(sms_error)}")
    
    # Send email if email available
    if target_email:
        try:
            email_content = await generate_email_content(target_analysis, target_name)
            await send_email(target_email, email_content)
            logger.info(f"Email sent successfully to {target_name}")
        except Exception as email_error:
            logger.error(f"Email sending failed for {target_name}: {str(email_error)}")
    
    # Generate and send voice message if phone number available and services configured
    if target_phone and elevenlabs_client and s3_client:
        try:
            # Generate voice message
            audio_file_path = await generate_voice_message(target_name, target_analysis)
            
            if audio_file_path:
                # Upload to S3
                audio_url = await upload_audio_to_s3(audio_file_path)
                
                if audio_url:
                    # Make voice call
                    call_result = await make_voice_call(target_phone, audio_url, target_name)
                    if call_result:
                        logger.info(f"Voice call initiated successfully to {target_name}: {call_result}")
                    else:
                        logger.warning(f"Voice call failed for {target_name}")
                else:
                    logger.warning(f"S3 upload failed - voice call skipped for {target_name}")
            else:
                logger.warning(f"Voice message generation failed - voice call skipped for {target_name}")
                
        except Exception as voice_error:
            logger.error(f"Voice outreach failed for {target_name}: {str(voice_error)}")
    else:
        missing_services = []
        if not target_phone:
            missing_services.append("phone number")
        if not elevenlabs_client:
            missing_services.append("ElevenLabs")
        if not s3_client:
            missing_services.append("S3")
        
        logger.info(f"Voice outreach skipped for {target_name} - missing: {', '.join(missing_services)}")
    
    logger.info(f"Outreach completed for target restaurant: {target_name}")

async def send_outreach_to_competitor(competitor_data: Dict, comp_analysis_xml: str):
    """Sends outreach to a competitor restaurant using scraped contact data."""
    logger.info(f"Starting enhanced outreach to competitor: {competitor_data['name']}")
    
    comp_analysis = parse_xml_analysis(comp_analysis_xml)
    if "error" in comp_analysis:
        logger.error(f"Failed to parse competitor analysis XML: {comp_analysis['error']}")
        return
    
    comp_name = competitor_data["name"]
    
    # ENHANCED: Prioritize scraped email from website over Google Places data
    comp_email = None
    comp_phone = None
    
    # First priority: scraped contact data from website
    if competitor_data.get("scraped_email"):
        comp_email = competitor_data["scraped_email"]
        logger.info(f"✅ Using scraped email for {comp_name}: {comp_email}")
    elif competitor_data.get("email"):
        comp_email = competitor_data["email"]
        logger.info(f"📞 Using Google Places email for {comp_name}: {comp_email}")
    
    # Phone number (prioritize scraped data)
    if competitor_data.get("scraped_phone"):
        comp_phone = competitor_data["scraped_phone"]
        logger.info(f"✅ Using scraped phone for {comp_name}: {comp_phone}")
    elif competitor_data.get("phone"):
        comp_phone = competitor_data["phone"]
        logger.info(f"📞 Using Google Places phone for {comp_name}: {comp_phone}")
    
    # Enhanced outreach with personalized content based on scraped data
    menu_items_count = len(competitor_data.get("menu_items", []))
    has_detailed_data = bool(competitor_data.get("website_data"))
    
    # Send SMS with enhanced context
    if comp_phone:
        try:
            # Generate personalized SMS content with competitive insights
            sms_content = await generate_competitor_sms_content(
                comp_analysis, comp_name, menu_items_count, has_detailed_data
            )
            await send_sms(comp_phone, sms_content)
            logger.info(f"✅ Enhanced SMS sent successfully to competitor {comp_name}")
        except Exception as sms_error:
            logger.error(f"❌ SMS sending failed for competitor {comp_name}: {str(sms_error)}")
    
    # Send email with detailed competitive analysis
    if comp_email:
        try:
            # Generate personalized email content with menu comparison
            email_content = await generate_competitor_email_content(
                comp_analysis, comp_name, competitor_data
            )
            await send_email(comp_email, email_content)
            logger.info(f"✅ Enhanced email sent successfully to competitor {comp_name}")
        except Exception as email_error:
            logger.error(f"❌ Email sending failed for competitor {comp_name}: {str(email_error)}")
    
    # Log outreach summary
    outreach_methods = []
    if comp_phone:
        outreach_methods.append("SMS")
    if comp_email:
        outreach_methods.append("Email")
    
    if outreach_methods:
        logger.info(f"🎯 Growth hack outreach completed for competitor '{comp_name}' via {', '.join(outreach_methods)}")
        logger.info(f"📊 Used data: email={'scraped' if competitor_data.get('scraped_email') else 'google'}, "
                   f"menu_items={menu_items_count}, detailed_data={has_detailed_data}")
    else:
        logger.warning(f"⚠️ No contact methods available for competitor {comp_name}")

async def generate_competitor_sms_content(analysis: Dict, restaurant_name: str, menu_items_count: int, has_detailed_data: bool) -> str:
    """Generate personalized SMS content for competitor outreach with competitive insights."""
    
    # Build context based on available data
    data_context = f"We analyzed {menu_items_count} menu items" if menu_items_count > 0 else "We analyzed your online presence"
    
    base_prompt = f"""Generate a friendly, professional SMS message for {restaurant_name} restaurant. 
    
    Context: {data_context} and found opportunities for growth. This is from a restaurant consulting service.
    
    Key insights from analysis:
    - Strengths: {', '.join(analysis.get('strengths', ['Strong local presence'])[:2])}
    - Opportunities: {', '.join(analysis.get('opportunities', ['Menu optimization'])[:2])}
    
    Requirements:
    - Keep under 160 characters
    - Sound helpful, not salesy
    - Mention specific opportunity
    - Include clear next step
    - Professional but approachable tone
    
    Example format: "Hi [Restaurant]! Noticed your great [strength] - there's an opportunity to [specific opportunity]. Quick 10min chat about boosting revenue? Free insights: [contact]"
    """
    
    try:
        client = get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": base_prompt}],
            max_tokens=100,
            temperature=0.7
        )
        
        sms_content = response.choices[0].message.content.strip()
        logger.info(f"Generated enhanced competitor SMS content for {restaurant_name}")
        return sms_content
        
    except Exception as e:
        logger.error(f"Failed to generate competitor SMS content: {str(e)}")
        # Fallback message
        return f"Hi {restaurant_name}! Your restaurant caught our attention - we found opportunities to boost revenue. Quick chat? Free restaurant growth insights available."

async def generate_competitor_email_content(analysis: Dict, restaurant_name: str, competitor_data: Dict) -> Dict:
    """Generate personalized email content for competitor outreach with detailed competitive analysis."""
    
    menu_items = competitor_data.get("menu_items", [])
    website_data = competitor_data.get("website_data", {})
    social_links = competitor_data.get("social_links", [])
    
    # Build detailed context
    menu_context = f"your {len(menu_items)} menu items" if menu_items else "your restaurant's online presence"
    social_context = f"and {len(social_links)} social media channels" if social_links else ""
    
    base_prompt = f"""Generate a professional, personalized email for {restaurant_name} restaurant.
    
    Context: We're a restaurant consulting service that analyzed {menu_context} {social_context} and found specific growth opportunities.
    
    Analysis insights:
    - Strengths: {', '.join(analysis.get('strengths', ['Strong local reputation']))}
    - Opportunities: {', '.join(analysis.get('opportunities', ['Menu optimization', 'Digital presence']))}
    - Recommendations: {', '.join(analysis.get('recommendations', ['Enhance online ordering'])[:3])}
    
    Email should include:
    1. Personalized subject line mentioning their restaurant name
    2. Professional greeting acknowledging their business
    3. Brief mention of what we analyzed (menu, website, etc.)
    4. 2-3 specific opportunities we identified
    5. Value proposition (how we help restaurants grow revenue)
    6. Soft call-to-action for free consultation
    7. Professional signature
    
    Tone: Professional, helpful, not pushy. Show we did real research on their business.
    Length: 150-200 words maximum.
    
    Return JSON format:
    {{
        "subject": "Specific opportunity for [Restaurant Name]",
        "body": "Email content here"
    }}
    """
    
    try:
        client = get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": base_prompt}],
            max_tokens=400,
            temperature=0.7
        )
        
        import json
        email_content = json.loads(response.choices[0].message.content.strip())
        logger.info(f"Generated enhanced competitor email content for {restaurant_name}")
        return email_content
        
    except Exception as e:
        logger.error(f"Failed to generate competitor email content: {str(e)}")
        # Fallback email
        return {
            "subject": f"Growth opportunity for {restaurant_name}",
            "body": f"Hi {restaurant_name} team,\n\nWe analyzed your restaurant's online presence and found several opportunities to boost revenue. As restaurant consultants, we help establishments like yours optimize their operations and increase profits.\n\nWe'd love to share our insights in a quick 15-minute call - no cost, no obligation.\n\nBest regards,\nRestaurant Growth Consultants"
        }
