#!/usr/bin/env python3
"""
Test script for Enhanced PDF Generation with LLMA-6 Strategic Analysis
Phase C: PDF Report Generation Testing

This script verifies that the enhanced PDF generator correctly handles:
1. LLMA-6 strategic analysis structure
2. Template rendering with nested data
3. Chart generation
4. Complete PDF creation pipeline
"""

import asyncio
import logging
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_mock_final_restaurant_output():
    """Create a comprehensive mock FinalRestaurantOutput for testing."""
    
    # Mock the required classes
    class MockExtractor:
        def __init__(self):
            self.restaurant_name = "Bella Vista Italian Bistro"
            self.address_canonical = "123 Main Street, Downtown, CA 94102"
            self.address_raw = "123 Main Street, Downtown, CA 94102"
            self.phone_canonical = "(555) 123-4567"
            self.phone_raw = "(555) 123-4567"
            self.canonical_url = "https://bellavista-bistro.com"
            self.cuisine_types = ["Italian", "Mediterranean"]
            self.price_range = "$$-$$$"
            self.description_short = "Authentic Italian dining with modern flair"
            self.description_long_ai_generated = "Bella Vista Italian Bistro offers an exceptional dining experience combining traditional Italian flavors with contemporary culinary techniques."
            
            # Mock menu items
            self.menu_items = [
                type('MenuItem', (), {
                    'name': 'Margherita Pizza',
                    'price': '$18.99',
                    'description': 'Fresh mozzarella, basil, tomato sauce',
                    'category': 'Pizza'
                })(),
                type('MenuItem', (), {
                    'name': 'Pasta Carbonara',
                    'price': '$22.99', 
                    'description': 'Pancetta, eggs, parmesan, black pepper',
                    'category': 'Pasta'
                })(),
                type('MenuItem', (), {
                    'name': 'Caesar Salad',
                    'price': '$14.99',
                    'description': 'Romaine, croutons, parmesan, caesar dressing',
                    'category': 'Salads'
                })(),
                type('MenuItem', (), {
                    'name': 'Tiramisu',
                    'price': '$9.99',
                    'description': 'Classic Italian dessert with coffee and mascarpone',
                    'category': 'Desserts'
                })()
            ]
            
            # Mock competitors
            self.competitors = [
                type('Competitor', (), {
                    'name': 'Mario\'s Italian Kitchen',
                    'rating': 4.3,
                    'review_count': 245
                })(),
                type('Competitor', (), {
                    'name': 'Piccolo Mondo',
                    'rating': 4.1,
                    'review_count': 189
                })(),
                type('Competitor', (), {
                    'name': 'Casa Italiana',
                    'rating': 4.5,
                    'review_count': 312
                })()
            ]
            
            # Mock screenshots
            self.screenshots = [
                type('Screenshot', (), {
                    's3_url': 'https://example.com/screenshot1.png',
                    'caption': 'Homepage Analysis',
                    'page_type': 'homepage'
                })(),
                type('Screenshot', (), {
                    's3_url': 'https://example.com/screenshot2.png',
                    'caption': 'Menu Page Optimization',
                    'page_type': 'menu'
                })()
            ]
            
            # Mock social media
            self.social_media_profiles = [
                {'platform': 'Instagram', 'url': 'https://instagram.com/bellavista', 'followers': 2500},
                {'platform': 'Facebook', 'url': 'https://facebook.com/bellavista', 'followers': 1800}
            ]
            
            # Mock operating hours
            self.operating_hours = [
                'Monday: 11:00 AM - 10:00 PM',
                'Tuesday: 11:00 AM - 10:00 PM', 
                'Wednesday: 11:00 AM - 10:00 PM',
                'Thursday: 11:00 AM - 10:00 PM',
                'Friday: 11:00 AM - 11:00 PM',
                'Saturday: 11:00 AM - 11:00 PM',
                'Sunday: 12:00 PM - 9:00 PM'
            ]
            
            # Mock Google My Business
            self.google_my_business = type('GMB', (), {
                'rating': 4.2,
                'user_ratings_total': 156
            })()
            
            # Mock menu PDFs
            self.menu_pdf_s3_urls = [
                'https://example.com/menu.pdf'
            ]
            
            # Mock extraction metadata
            self.extraction_metadata = type('Metadata', (), {
                'final_quality_score': 8.7,
                'total_duration_seconds': 245.6,
                'total_cost_usd': 1.45,
                'phases_completed': 4
            })()
            
            # LLMA-6 Strategic Analysis (Enhanced Structure)
            self.llm_strategic_analysis = {
                "executive_hook": {
                    "hook_statement": "Bella Vista Italian Bistro has strong fundamentals but is missing $3,200-$6,500 in monthly revenue due to digital optimization gaps and untapped customer engagement opportunities.",
                    "biggest_opportunity_teaser": "Google My Business optimization could increase foot traffic by 25-40% within 60 days"
                },
                "competitive_landscape_summary": {
                    "introduction": "Operating in a competitive Italian dining market, Bella Vista shows strong potential for market leadership with strategic digital enhancements.",
                    "detailed_comparison_text": "Analysis of 3 direct competitors reveals that Bella Vista has superior menu variety and pricing strategy, but lags in digital presence optimization. While competitors like Casa Italiana (4.5★, 312 reviews) lead in online reputation, Bella Vista's authentic offerings and strategic location provide excellent foundation for growth. The local Italian restaurant market shows 15-20% annual growth, with digital-savvy establishments capturing disproportionate market share.",
                    "key_takeaway_for_owner": "You have excellent product-market fit and operational foundations. Strategic focus on digital optimization and customer engagement will position you as the market leader."
                },
                "top_3_prioritized_opportunities": [
                    {
                        "priority_rank": 1,
                        "opportunity_title": "Google My Business & Local SEO Optimization",
                        "current_situation_and_problem": "Your GMB listing lacks optimization elements that competitors are leveraging. Missing business attributes, limited photo variety, and inconsistent posting schedule are limiting local search visibility. Competitors rank higher for key searches like 'Italian restaurant near me' despite your superior offerings.",
                        "detailed_recommendation": "Implement comprehensive GMB optimization including: complete business information, weekly photo updates, regular posts about specials, customer Q&A management, and review response automation. Add business attributes like 'outdoor seating,' 'wine selection,' and 'romantic atmosphere.' Create location-specific content targeting neighborhood keywords.",
                        "estimated_revenue_or_profit_impact": "Conservative projections: 25-40% increase in local search visibility leading to 18-25 additional weekly customers. At $45 average ticket, this translates to $3,240-$4,500 additional monthly revenue with 75% gross margin contributing $2,430-$3,375 monthly profit.",
                        "ai_solution_pitch": "Our AI OrderFlow Manager automates GMB optimization, tracks competitor changes, manages review responses, and optimizes posting schedules for maximum visibility. Never miss a local search opportunity again.",
                        "implementation_timeline": "2-3 Weeks",
                        "difficulty_level": "Low to Medium (Mostly Strategic Setup)",
                        "visual_evidence_suggestion": {
                            "idea_for_visual": "GMB audit comparison showing current vs. optimized listing with projected visibility improvements",
                            "relevant_screenshot_s3_url_from_input": "https://example.com/screenshot1.png"
                        }
                    },
                    {
                        "priority_rank": 2,
                        "opportunity_title": "Customer Experience & Review Generation System",
                        "current_situation_and_problem": "Strong food quality but inconsistent review generation and customer retention. 4.2★ rating with only 156 reviews suggests satisfied customers aren't being prompted to share experiences. Competitors with similar quality have 2x more reviews, indicating better customer engagement systems.",
                        "detailed_recommendation": "Implement systematic customer experience optimization: train staff on review request techniques, create QR code table tents linking to review platforms, develop email follow-up campaigns for reservation customers, and establish customer loyalty program with review incentives. Focus on creating remarkable moments that naturally generate word-of-mouth marketing.",
                        "estimated_revenue_or_profit_impact": "Improved ratings (4.2→4.5★) and doubled review volume typically increases customer interest by 15-25%. Combined with loyalty program, expect 20-30% increase in repeat customers contributing $2,800-$4,200 additional monthly revenue.",
                        "ai_solution_pitch": "Review Amplify AI automates review requests via SMS/email, tracks customer satisfaction metrics, identifies at-risk customers for proactive service recovery, and generates personalized retention campaigns.",
                        "implementation_timeline": "3-4 Weeks",
                        "difficulty_level": "Medium (Requires Staff Training & System Setup)",
                        "visual_evidence_suggestion": {
                            "idea_for_visual": "Customer journey map showing optimized touchpoints for review generation and retention",
                            "relevant_screenshot_s3_url_from_input": None
                        }
                    },
                    {
                        "priority_rank": 3,
                        "opportunity_title": "Social Media & Content Marketing Automation",
                        "current_situation_and_problem": "Limited social media presence (2,500 Instagram, 1,800 Facebook followers) with irregular posting and minimal engagement. Missing opportunities to showcase menu items, behind-the-scenes content, and customer testimonials. Competitors with active social presence report 20-30% higher customer acquisition from social channels.",
                        "detailed_recommendation": "Develop comprehensive social media strategy: daily Instagram Stories showcasing fresh ingredients and preparation, weekly menu highlight posts, customer feature content, seasonal promotion campaigns, and local community engagement. Implement user-generated content campaigns encouraging customers to share their dining experiences.",
                        "estimated_revenue_or_profit_impact": "Active social presence typically drives 10-20% increase in new customer acquisition. Targeted local social advertising and organic engagement could generate 12-18 additional weekly customers, contributing $2,160-$3,240 monthly revenue.",
                        "ai_solution_pitch": "Social Spark Bot creates personalized content calendars, automates posting schedules, generates captions optimized for engagement, and tracks performance metrics to continuously improve social ROI.",
                        "implementation_timeline": "4-6 Weeks",
                        "difficulty_level": "Medium (Content Creation & Consistency Required)",
                        "visual_evidence_suggestion": {
                            "idea_for_visual": "Social media audit showing content gaps and engagement opportunities compared to successful competitors",
                            "relevant_screenshot_s3_url_from_input": "https://example.com/screenshot2.png"
                        }
                    }
                ],
                "premium_analysis_teasers": [
                    {
                        "premium_feature_title": "Real-Time Competitor Price & Menu Intelligence",
                        "compelling_teaser_hook": "Get instant alerts when Mario's Italian Kitchen or Casa Italiana change their pricing, launch new menu items, or run promotions. Stay ahead with first-mover advantage.",
                        "value_proposition": "Our AI monitors competitor websites, social media, and review mentions 24/7, providing strategic recommendations for pricing adjustments and menu positioning."
                    },
                    {
                        "premium_feature_title": "Predictive Customer Demand Analytics",
                        "compelling_teaser_hook": "Know exactly which menu items will be popular before the weekend rush. Our AI analyzes weather, events, social trends, and historical patterns to optimize inventory and staffing.",
                        "value_proposition": "Reduce food waste by 25-40% while ensuring you never run out of popular items during peak demand periods."
                    },
                    {
                        "premium_feature_title": "Automated Revenue Optimization Engine",
                        "compelling_teaser_hook": "Maximize every dollar with AI that adjusts pricing, suggests daily specials, and optimizes table turnover based on real-time demand and competitor actions.",
                        "value_proposition": "Increase average transaction value by 8-15% through intelligent upselling recommendations and dynamic pricing strategies."
                    }
                ],
                "immediate_action_items_quick_wins": [
                    {
                        "action_item": "Update GMB listing with complete business hours, phone number, and add 5 new high-quality food photos",
                        "rationale_and_benefit": "Takes 30 minutes but can improve local search ranking within 48 hours, directly impacting weekend foot traffic"
                    },
                    {
                        "action_item": "Respond to all reviews from the past 3 months with personalized, professional messages",
                        "rationale_and_benefit": "Shows active engagement to potential customers and improves review platform algorithms favoring your restaurant"
                    },
                    {
                        "action_item": "Create QR code linking to your Google review page and place on every table",
                        "rationale_and_benefit": "Satisfied customers need easy review access - can double review generation within 2 weeks"
                    },
                    {
                        "action_item": "Post one high-quality food photo on Instagram with location tag and relevant hashtags",
                        "rationale_and_benefit": "Immediately increases local discovery and showcases menu quality to potential customers browsing location tags"
                    },
                    {
                        "action_item": "Set up Google Posts schedule for weekly specials and events announcements",
                        "rationale_and_benefit": "Free marketing that appears directly in search results - competitors doing this get 15-20% more clicks"
                    }
                ],
                "engagement_and_consultation_questions": [
                    "What's your biggest challenge with attracting new customers versus retaining existing ones?",
                    "How do you currently track which marketing efforts bring in the most customers?",
                    "What's your target monthly revenue growth, and what timeline feels realistic for implementation?",
                    "Which competitors do you see as your biggest threats, and what advantages do you have over them?",
                    "How comfortable is your team with implementing new technology and digital marketing strategies?"
                ],
                "forward_thinking_strategic_insights": {
                    "untapped_potential_and_innovation_ideas": [
                        "Consider implementing AI-powered inventory management to reduce food waste by 30-40% while optimizing cash flow",
                        "Explore partnerships with local wine shops or breweries for cross-promotional events that expand customer base",
                        "Investigate loyalty program automation that personalizes offers based on customer dining patterns and preferences",
                        "Look into dynamic pricing strategies for peak/off-peak hours to maximize revenue during high-demand periods",
                        "Consider implementing tableside ordering technology to improve table turnover and reduce labor costs"
                    ],
                    "long_term_vision_alignment_thoughts": [
                        "Building a data-driven operation now positions you for potential second location expansion within 18-24 months",
                        "Investing in customer relationship technology creates competitive moats as the restaurant industry digitalizes",
                        "Developing strong online presence and automation provides resilience against economic downturns and supply chain disruptions",
                        "Creating systematic approaches to quality and customer service supports franchise or licensing opportunities in the future"
                    ],
                    "consultants_core_empowerment_message": "Bella Vista Italian Bistro has all the ingredients for exceptional success - authentic cuisine, strategic location, and clear market positioning. The digital optimization opportunities we've identified aren't just theoretical improvements; they're proven strategies that will generate immediate, measurable results. Your passion for Italian cuisine combined with smart business systems will create a restaurant that not only thrives today but builds lasting value for the future. Success isn't a matter of if, but when you implement these strategic improvements."
                }
            }
    
    return MockExtractor()

async def test_enhanced_pdf_generation():
    """Test the complete enhanced PDF generation pipeline."""
    logger.info("🧪 Starting Enhanced PDF Generation Test with LLMA-6 Integration")
    
    try:
        # Import the enhanced PDF generator
        from restaurant_consultant.pdf_generator_module import RestaurantReportGenerator
        
        # Initialize the generator
        pdf_generator = RestaurantReportGenerator()
        logger.info("✅ Enhanced PDF generator initialized")
        
        # Create mock restaurant data
        mock_data = create_mock_final_restaurant_output()
        logger.info("✅ Mock LLMA-6 restaurant data created")
        
        # Test the enhanced PDF generation
        logger.info("📄 Testing enhanced PDF generation with LLMA-6 data...")
        pdf_result = await pdf_generator.generate_pdf_report(mock_data)
        
        # Analyze results
        if pdf_result.get('success'):
            logger.info("🎉 Enhanced PDF generation successful!")
            logger.info(f"   📄 PDF size: {pdf_result.get('pdf_size_bytes', 0):,} bytes")
            logger.info(f"   📊 Charts generated: {pdf_result.get('charts_generated', 0)}")
            logger.info(f"   🎯 Opportunities included: {pdf_result.get('opportunities_count', 0)}")
            logger.info(f"   ⚡ Action items: {pdf_result.get('action_items_included', 0)}")
            logger.info(f"   ❓ Consultation questions: {pdf_result.get('consultation_questions_included', 0)}")
            logger.info(f"   💎 Premium teasers: {pdf_result.get('premium_teasers_included', 0)}")
            logger.info(f"   📸 Screenshots: {pdf_result.get('screenshots_included', 0)}")
            logger.info(f"   🏆 Analysis version: {pdf_result.get('strategic_analysis_version', 'Unknown')}")
            logger.info(f"   📈 Comprehensiveness score: {pdf_result.get('analysis_comprehensiveness_score', 'N/A')}")
            
            if pdf_result.get('pdf_s3_url'):
                logger.info(f"   🔗 S3 URL: {pdf_result['pdf_s3_url']}")
            else:
                logger.info("   ⚠️ PDF generated locally (S3 upload not configured)")
                
        else:
            logger.error("❌ Enhanced PDF generation failed!")
            logger.error(f"   Error: {pdf_result.get('error', 'Unknown error')}")
            return False
        
        # Test fallback analysis
        logger.info("🧪 Testing LLMA-6 fallback analysis...")
        fallback_analysis = pdf_generator._create_fallback_strategic_analysis()
        
        # Verify fallback structure
        required_sections = [
            'executive_hook',
            'competitive_landscape_summary',
            'top_3_prioritized_opportunities',
            'premium_analysis_teasers',
            'immediate_action_items_quick_wins',
            'engagement_and_consultation_questions',
            'forward_thinking_strategic_insights'
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in fallback_analysis:
                missing_sections.append(section)
        
        if not missing_sections:
            logger.info("✅ Fallback analysis has all required LLMA-6 sections")
            
            # Check nested structures
            if isinstance(fallback_analysis.get('executive_hook'), dict):
                logger.info("✅ Executive hook has proper nested structure")
            
            opportunities = fallback_analysis.get('top_3_prioritized_opportunities', [])
            if len(opportunities) == 3:
                logger.info("✅ Fallback includes 3 prioritized opportunities")
                
                # Check opportunity structure
                first_opp = opportunities[0]
                required_opp_fields = [
                    'priority_rank', 'opportunity_title', 'current_situation_and_problem',
                    'detailed_recommendation', 'estimated_revenue_or_profit_impact',
                    'ai_solution_pitch', 'implementation_timeline', 'difficulty_level'
                ]
                
                missing_opp_fields = [field for field in required_opp_fields if field not in first_opp]
                if not missing_opp_fields:
                    logger.info("✅ Opportunity structure is complete")
                else:
                    logger.warning(f"⚠️ Missing opportunity fields: {missing_opp_fields}")
            
            forward_insights = fallback_analysis.get('forward_thinking_strategic_insights', {})
            if isinstance(forward_insights, dict) and 'untapped_potential_and_innovation_ideas' in forward_insights:
                logger.info("✅ Forward-thinking insights have proper structure")
        else:
            logger.error(f"❌ Fallback analysis missing sections: {missing_sections}")
            return False
        
        # Test template elements
        logger.info("🧪 Testing template LLMA-6 integration...")
        template_path = pdf_generator.templates_dir / "main_report.html"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            llma6_template_elements = [
                '{{ biggest_opportunity_teaser }}',
                '{{ competitive_introduction }}',
                '{{ competitive_key_takeaway }}',
                '{{ opportunity.opportunity_title }}',
                '{{ opportunity.current_situation_and_problem }}',
                '{{ opportunity.detailed_recommendation }}',
                '{{ opportunity.estimated_revenue_or_profit_impact }}',
                '{{ opportunity.ai_solution_pitch }}',
                '{{ empowerment_message }}',
                '{{ llm_analysis_version }}'
            ]
            
            found_elements = [elem for elem in llma6_template_elements if elem in template_content]
            logger.info(f"✅ Template LLMA-6 elements found: {len(found_elements)}/{len(llma6_template_elements)}")
            
            if len(found_elements) >= len(llma6_template_elements) * 0.8:
                logger.info("✅ Template successfully enhanced for LLMA-6!")
            else:
                logger.warning("⚠️ Template may be missing some LLMA-6 elements")
        
        logger.info("🎉 Enhanced PDF Generation Test Completed Successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced PDF generation test failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main test function."""
    logger.info("🚀 Enhanced PDF Generation Testing Suite")
    logger.info("="*60)
    
    success = await test_enhanced_pdf_generation()
    
    logger.info("="*60)
    if success:
        logger.info("🎉 All tests passed! Enhanced PDF generation with LLMA-6 is ready!")
    else:
        logger.error("❌ Some tests failed. Check the logs above for details.")
        
    return success

if __name__ == "__main__":
    asyncio.run(main()) 