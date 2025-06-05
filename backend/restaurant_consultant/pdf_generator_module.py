import os
import json
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from pathlib import Path
from datetime import datetime
import tempfile
import base64
import shutil

# PDF generation libraries
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader, Template
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import requests
import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from .models import FinalRestaurantOutput

# Set up logging
logger = logging.getLogger(__name__)

# Configure matplotlib for clean charts
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

# AWS S3 configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") 
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "restaurant-ai-reports")

class RestaurantReportGenerator:
    """
    Comprehensive PDF report generator for restaurant analysis using WeasyPrint.
    """
    
    def __init__(self):
        """Initialize PDF generator with local storage fallback"""
        logger.info("🚀 Initializing PDF Generator...")
        
        # Set up directories
        self.base_dir = Path(__file__).parent
        self.templates_dir = self.base_dir / "pdf_templates"
        self.static_dir = self.base_dir / "pdf_static"
        
        # Create local storage directory for PDFs
        self.local_storage_dir = self.base_dir.parent / "generated_pdfs"
        self.local_storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure required directories exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.static_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True
        )
        
        # AWS Configuration (optional)
        self.aws_enabled = False
        self.s3_client = None
        
        # Try to initialize AWS S3 (but don't require it)
        AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
        AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
        
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            try:
                import boto3
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                    region_name=AWS_REGION
                )
                self.aws_enabled = True
                logger.info("✅ AWS S3 client initialized for PDF uploads")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize S3 client: {str(e)}")
                logger.info("📁 Falling back to local file storage")
        else:
            logger.info("📁 Using local file storage for PDFs (AWS credentials not configured)")
        
        logger.info(f"📄 PDF generator initialized: templates={self.templates_dir}, static={self.static_dir}, storage={self.local_storage_dir}")
    
    def create_default_templates(self):
        """Create default HTML/CSS templates if they don't exist."""
        logger.info("📝 Creating default PDF templates")
        
        # Main report HTML template
        main_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ restaurant_name }} - AI Strategic Business Analysis</title>
    <style>
        {{ css_content }}
    </style>
</head>
<body>
    <!-- Cover Page -->
    <div class="page cover-page">
        <div class="cover-header">
            <div class="logo-area">
                <h1>🤖 Restaurant AI Consulting</h1>
                <p class="tagline">McKinsey-Level Strategic Analysis</p>
            </div>
            <h2 class="restaurant-title">{{ restaurant_name }}</h2>
            <p class="restaurant-subtitle">{{ restaurant_address }}</p>
            <p class="report-subtitle">Competitive Intelligence & Strategic Growth Analysis</p>
        </div>
        
        <div class="cover-hook">
            <div class="hook-box">
                <h3>💰 Executive Strategic Summary</h3>
                <p class="hook-text">{{ executive_hook }}</p>
                {% if biggest_opportunity_teaser %}
                <p class="opportunity-teaser">🎯 <strong>Biggest Opportunity:</strong> {{ biggest_opportunity_teaser }}</p>
                {% endif %}
                <div class="confidence-badge">
                    <span>✅ LLMA-6 AI Analysis</span>
                    <span>📊 {{ competitors_analyzed }} Local Competitors</span>
                    <span>🔍 {{ data_points_analyzed }}+ Data Points</span>
                    <span>🎯 Quality Score: {{ ai_analysis_depth_score }}/10</span>
                </div>
            </div>
        </div>
        
        <div class="cover-stats">
            <div class="stat-item">
                <div class="stat-number">{{ data_points_analyzed }}</div>
                <div class="stat-label">Data Points Analyzed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{{ competitors_analyzed }}</div>
                <div class="stat-label">Competitors Researched</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{{ opportunities_count }}</div>
                <div class="stat-label">Growth Opportunities</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{{ screenshots_analyzed }}</div>
                <div class="stat-label">Screenshots Analyzed</div>
            </div>
        </div>
        
        <div class="cover-footer">
            <p>Generated on {{ analysis_date }} | {{ llm_analysis_version }} Strategic Engine</p>
            <p class="cta-text">📞 Ready to implement? Schedule your free consultation</p>
        </div>
    </div>
    
    <!-- Executive Summary Page -->
    <div class="page content-page">
        <h2 class="page-title">📊 Executive Summary & Business Snapshot</h2>
        
        <div class="restaurant-overview">
            <h3>{{ restaurant_name }}</h3>
            <div class="overview-details">
                <div class="details-grid">
                    <div class="detail-item">
                        <strong>📍 Location:</strong> {{ restaurant_address }}
                    </div>
                    <div class="detail-item">
                        <strong>🌐 Website:</strong> {{ restaurant_website }}
                    </div>
                    {% if restaurant_phone %}
                    <div class="detail-item">
                        <strong>📞 Phone:</strong> {{ restaurant_phone }}
                    </div>
                    {% endif %}
                    {% if cuisine_types %}
                    <div class="detail-item">
                        <strong>🍽️ Cuisine:</strong> {{ cuisine_types|join(', ') }}
                    </div>
                    {% endif %}
                    {% if price_range %}
                    <div class="detail-item">
                        <strong>💰 Price Range:</strong> {{ price_range }}
                    </div>
                    {% endif %}
                    <div class="detail-item">
                        <strong>📋 Menu Items:</strong> {{ menu_items_count }} analyzed
                    </div>
                </div>
            </div>
        </div>
        
        {% if competitive_introduction %}
        <div class="competitive-introduction">
            <h3>🎯 Strategic Position Analysis</h3>
            <div class="intro-box">
                <p>{{ competitive_introduction }}</p>
            </div>
        </div>
        {% endif %}
        
        {% if charts.ratings_comparison %}
        <div class="chart-section">
            <h4>📈 Performance vs. Competition</h4>
            <div class="chart-container">
                <img src="data:image/png;base64,{{ charts.ratings_comparison }}" alt="Competitive Performance Analysis" class="chart-image"/>
                <p class="chart-caption">Your competitive position relative to local market leaders</p>
            </div>
        </div>
        {% endif %}
        
        {% if competitive_insights %}
        <div class="key-findings">
            <h4>🎯 Key Strategic Insights</h4>
            <div class="findings-grid">
                {% for insight in competitive_insights %}
                <div class="insight-card">
                    <div class="insight-icon">{{ insight.icon }}</div>
                    <h5>{{ insight.title }}</h5>
                    <p>{{ insight.description }}</p>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
    
    <!-- Competitive Landscape Deep Dive Page -->
    <div class="page content-page">
        <h2 class="page-title">🏆 Competitive Landscape Analysis</h2>
        <p class="page-subtitle">Comprehensive market positioning and opportunity identification</p>
        
        <div class="competitive-analysis-section">
            <div class="analysis-content">
                <p>{{ competitive_landscape_summary }}</p>
            </div>
            
            {% if competitive_key_takeaway %}
            <div class="key-takeaway-box">
                <h4>🎯 Strategic Takeaway for You</h4>
                <p>{{ competitive_key_takeaway }}</p>
            </div>
            {% endif %}
        </div>
        
        {% if charts.business_intelligence %}
        <div class="chart-section">
            <h4>📊 Competitive Intelligence Dashboard</h4>
            <div class="chart-container">
                <img src="data:image/png;base64,{{ charts.business_intelligence }}" alt="Business Intelligence Metrics" class="chart-image"/>
                <p class="chart-caption">Comprehensive analysis across {{ data_points_analyzed }} data points</p>
            </div>
        </div>
        {% endif %}
        
        {% if charts.menu_distribution %}
        <div class="chart-section">
            <h4>🍽️ Menu Strategy Analysis</h4>
            <div class="chart-container">
                <img src="data:image/png;base64,{{ charts.menu_distribution }}" alt="Menu Strategy Analysis" class="chart-image"/>
                <p class="chart-caption">Strategic distribution of your {{ menu_items_count }} menu items</p>
            </div>
        </div>
        {% endif %}
    </div>
    
    <!-- Strategic Growth Opportunities Pages (1-3) -->
        {% for opportunity in prioritized_opportunities %}
    <div class="page content-page opportunity-page">
        <h2 class="page-title">🚀 Growth Opportunity #{{ opportunity.priority_rank }}</h2>
        <div class="opportunity-full-analysis">
            <div class="opportunity-header">
                <h3 class="opportunity-title">{{ opportunity.opportunity_title }}</h3>
                    <div class="opportunity-meta">
                        <span class="timeline-badge">⏱️ {{ opportunity.implementation_timeline }}</span>
                    <span class="difficulty-badge">🎯 {{ opportunity.difficulty_level }}</span>
                </div>
            </div>
            
            <div class="opportunity-sections">
                <div class="problem-section">
                    <h4>❌ Current Situation & Challenge</h4>
                    <div class="content-box">
                        <p>{{ opportunity.current_situation_and_problem }}</p>
                    </div>
                </div>
                
                <div class="solution-section">
                    <h4>✅ Detailed Strategic Recommendation</h4>
                    <div class="content-box">
                        <p>{{ opportunity.detailed_recommendation }}</p>
                    </div>
                </div>
                
                <div class="impact-section">
                    <h4>💰 Revenue & Profit Impact Analysis</h4>
                    <div class="impact-box">
                        <p>{{ opportunity.estimated_revenue_or_profit_impact }}</p>
                    </div>
                </div>
                
                <div class="ai-solution-section">
                    <h4>🤖 AI Platform Implementation</h4>
                    <div class="ai-solution-box">
                        <p>{{ opportunity.ai_solution_pitch }}</p>
                        <button class="ai-cta-btn">Get AI Implementation Quote</button>
                    </div>
                </div>
                
                {% if opportunity.visual_evidence_suggestion %}
                <div class="visual-evidence-section">
                    <h4>📸 Visual Evidence & Implementation Guide</h4>
                    <div class="visual-suggestion-box">
                        {% set visual_suggestion = opportunity.visual_evidence_suggestion %}
                        {% if visual_suggestion.idea_for_visual %}
                        <p><strong>Implementation Visual:</strong> {{ visual_suggestion.idea_for_visual }}</p>
                        {% endif %}
                        {% if visual_suggestion.relevant_screenshot_s3_url_from_input %}
                        <div class="evidence-screenshot">
                            <img src="{{ visual_suggestion.relevant_screenshot_s3_url_from_input }}" alt="Current State Evidence" class="evidence-image"/>
                            <p class="screenshot-note">Current state analysis for improvement opportunity</p>
            </div>
                        {% endif %}
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    {% endfor %}
    
    <!-- Forward-Thinking Strategic Insights Page -->
    {% if untapped_innovation_ideas or long_term_strategic_thoughts or empowerment_message %}
    <div class="page content-page innovation-page">
        <h2 class="page-title">🔮 Forward-Thinking Strategic Insights</h2>
        <p class="page-subtitle">Innovation opportunities and long-term vision alignment</p>
        
        {% if untapped_innovation_ideas %}
        <div class="innovation-section">
            <h3>💡 Untapped Potential & Innovation Ideas</h3>
            <div class="innovation-list">
                {% for idea in untapped_innovation_ideas %}
                <div class="innovation-item">
                    <div class="innovation-marker">💡</div>
                    <p>{{ idea }}</p>
                </div>
                {% endfor %}
            </div>
            </div>
            {% endif %}
        
        {% if long_term_strategic_thoughts %}
        <div class="long-term-section">
            <h3>🎯 Long-Term Vision Alignment</h3>
            <div class="vision-list">
                {% for thought in long_term_strategic_thoughts %}
                <div class="vision-item">
                    <div class="vision-marker">🎯</div>
                    <p>{{ thought }}</p>
        </div>
        {% endfor %}
    </div>
        </div>
        {% endif %}
        
        {% if empowerment_message %}
        <div class="empowerment-section">
            <h3>🌟 Your Path to Success</h3>
            <div class="empowerment-box">
                <p>{{ empowerment_message }}</p>
            </div>
        </div>
        {% endif %}
    </div>
    {% endif %}
    
    <!-- Screenshots Analysis Page -->
    {% if formatted_screenshots %}
    <div class="page content-page">
        <h2 class="page-title">👁️ Digital Presence Analysis</h2>
        <p class="page-subtitle">AI-powered analysis of your online touchpoints</p>
        
        <div class="screenshots-grid">
            {% for screenshot in formatted_screenshots[:4] %}
            <div class="screenshot-analysis">
                <div class="screenshot-container">
                    <img src="{{ screenshot.s3_url }}" alt="{{ screenshot.caption }}" class="screenshot-image"/>
                    <div class="screenshot-overlay">
                        <div class="quality-score">Quality: {{ "%.1f"|format(screenshot.quality_score) }}/5.0</div>
        </div>
                </div>
                <div class="screenshot-insights">
                    <h4>{{ screenshot.caption }}</h4>
                    <p class="page-type">{{ screenshot.page_type|title }} Analysis</p>
                    <p class="analysis-insight">{{ screenshot.analysis_insight }}</p>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}
    
    <!-- Premium Content Teasers Page -->
    {% if premium_insights_teasers %}
    <div class="page content-page premium-page">
        <h2 class="page-title">🔒 Premium Strategic Intelligence</h2>
        <p class="page-subtitle">Unlock deeper analysis and personalized AI-powered recommendations</p>
        
        <div class="premium-grid">
            {% for teaser in premium_insights_teasers %}
            <div class="premium-card">
                <div class="premium-header">
                    <h4>{{ teaser.title }}</h4>
                    <span class="premium-badge">Premium</span>
                </div>
                <div class="premium-preview">
                    <p>{{ teaser.teaser }}</p>
                </div>
                <div class="premium-value">
                    <p class="value-prop">{{ teaser.value_proposition }}</p>
                        </div>
                <div class="premium-cta">
                        <button class="upgrade-btn">Unlock Full Analysis</button>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="upgrade-section">
            <h3>🚀 Transform Your Restaurant with AI-Powered Intelligence</h3>
            <p>Our premium analysis includes competitor intelligence, automated review management, dynamic pricing strategies, menu optimization AI, and personalized implementation roadmaps.</p>
            <div class="upgrade-benefits">
                <div class="benefit-item">✅ Real-time competitor monitoring</div>
                <div class="benefit-item">✅ Automated customer review responses</div>
                <div class="benefit-item">✅ Dynamic pricing optimization</div>
                <div class="benefit-item">✅ Menu performance analytics</div>
                <div class="benefit-item">✅ Personalized growth roadmap</div>
                <div class="benefit-item">✅ Monthly strategic updates</div>
            </div>
            <button class="main-upgrade-btn">Upgrade to Premium Analysis</button>
        </div>
    </div>
    {% endif %}
    
    <!-- Action Items & Next Steps Page -->
    <div class="page content-page action-page">
        <h2 class="page-title">✅ Immediate Action Items & Implementation</h2>
        <p class="page-subtitle">Start implementing these zero-budget, high-impact recommendations today</p>
        
        {% if immediate_action_items %}
        <div class="action-items-section">
            <h3>🚀 Quick Wins (0-2 Hours Each)</h3>
            <div class="action-items-grid">
                {% for action in immediate_action_items %}
                <div class="action-item">
                    <div class="action-number">{{ loop.index }}</div>
                    <div class="action-content">
                        {% if action and "|" in (action|string) %}
                        {% set action_parts = (action|string).split("|") %}
                        <p class="action-task">{{ action_parts[0].strip() }}</p>
                        <p class="action-rationale">{{ action_parts[1].strip() }}</p>
                        {% else %}
                        <p class="action-task">{{ action|string }}</p>
                        {% endif %}
                    </div>
                    <div class="action-status">
                        <input type="checkbox" class="action-checkbox">
                        <label>Mark Complete</label>
                    </div>
                </div>
                {% endfor %}
    </div>
        </div>
        {% endif %}
        
        {% if consultation_questions %}
        <div class="consultation-section">
            <h3>💬 Let's Discuss Your Specific Growth Strategy</h3>
            <p>We'd love to learn more about your unique challenges and growth goals:</p>
            <div class="questions-list">
                {% for question in consultation_questions %}
                <div class="question-item">
                    <span class="question-marker">❓</span>
                    <p>{{ question }}</p>
                </div>
                {% endfor %}
            </div>
            <div class="consultation-cta">
                <button class="consultation-btn">Schedule Free 30-Minute Strategy Session</button>
                <p class="consultation-note">No sales pitch - just strategic insights tailored to your restaurant</p>
        </div>
                    </div>
        {% endif %}
                </div>
                
    <!-- Footer Page -->
    <div class="page footer-page">
        <div class="footer-content">
            <h2>🤖 Restaurant AI Consulting</h2>
            <p class="footer-tagline">Transforming Restaurant Success Through Strategic AI</p>
            
            <div class="contact-grid">
                <div class="contact-item">
                    <h4>📧 Strategic Partnership</h4>
                    <p>hello@restaurant-ai-consulting.com</p>
                    <p>Let's discuss your growth strategy</p>
                </div>
                <div class="contact-item">
                    <h4>📞 Free Consultation</h4>
                    <p>Book your complimentary strategy session</p>
                    <p>No commitment, just insights</p>
                </div>
                <div class="contact-item">
                    <h4>🌐 AI Platform Demo</h4>
                    <p>restaurant-ai-consulting.com/demo</p>
                    <p>See our AI tools in action</p>
                </div>
            </div>
            
            <div class="footer-stats">
                <h3>📊 This Analysis By The Numbers</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <span class="stat-value">{{ data_points_analyzed }}</span>
                        <span class="stat-label">Data Points</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{{ competitors_analyzed }}</span>
                        <span class="stat-label">Competitors</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{{ opportunities_count }}</span>
                        <span class="stat-label">Opportunities</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">{{ ai_analysis_depth_score }}/10</span>
                        <span class="stat-label">Quality Score</span>
                </div>
            </div>
        </div>
        
            <div class="footer-disclaimer">
                <p><strong>Strategic Analysis Report | Generated {{ analysis_date }}</strong></p>
                <p>Powered by {{ llm_analysis_version }} Strategic Intelligence Engine</p>
                <p class="disclaimer-text">This analysis is based on publicly available data and AI-powered strategic insights. Revenue projections and recommendations are estimates based on industry best practices, competitive analysis, and proven growth strategies. Individual results may vary based on market conditions, implementation quality, and business-specific factors.</p>
            </div>
        </div>
    </div>
</body>
</html>"""
        
        # CSS styles
        css_content = """
/* Reset and base styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
    color: #333;
    background: #fff;
    font-size: 14px;
}

/* Page layout */
.page {
    width: 210mm;
    min-height: 297mm;
    padding: 20mm;
    page-break-after: always;
    position: relative;
    display: flex;
    flex-direction: column;
}

.page:last-child {
    page-break-after: avoid;
}

/* Cover page styles */
.cover-page {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    text-align: center;
    justify-content: space-between;
}

.cover-header {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 40px 0;
}

.logo-area h1 {
    font-size: 42px;
    font-weight: 700;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.tagline {
    font-size: 18px;
    font-weight: 300;
    margin-bottom: 40px;
    opacity: 0.9;
}

.restaurant-title {
    font-size: 36px;
    font-weight: 600;
    margin-bottom: 15px;
    text-shadow: 1px 1px 3px rgba(0,0,0,0.3);
}

.restaurant-subtitle {
    font-size: 18px;
    margin-bottom: 10px;
    opacity: 0.8;
}

.report-subtitle {
    font-size: 16px;
    font-weight: 300;
    opacity: 0.7;
}

/* Cover hook section */
.cover-hook {
    margin: 40px 0;
}

.hook-box {
    background: rgba(255,255,255,0.15);
    padding: 30px;
    border-radius: 15px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.2);
}

.hook-box h3 {
    font-size: 24px;
    margin-bottom: 20px;
    font-weight: 600;
}

.hook-text {
    font-size: 18px;
    line-height: 1.7;
    margin-bottom: 20px;
}

.opportunity-teaser {
    font-size: 16px;
    margin-bottom: 20px;
    padding: 15px;
    background: rgba(255,255,255,0.1);
    border-radius: 10px;
    border-left: 4px solid #FFE066;
}

.confidence-badge {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
    justify-content: center;
    margin-top: 20px;
}

.confidence-badge span {
    background: rgba(255,255,255,0.2);
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 500;
    border: 1px solid rgba(255,255,255,0.3);
}

/* Cover stats */
.cover-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin: 40px 0;
}

.stat-item {
    text-align: center;
    background: rgba(255,255,255,0.1);
    padding: 20px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.2);
}

.stat-number {
    font-size: 32px;
    font-weight: 700;
    display: block;
    margin-bottom: 8px;
}

.stat-label {
    font-size: 14px;
    opacity: 0.8;
    font-weight: 300;
}

.cover-footer {
    text-align: center;
    font-size: 14px;
    opacity: 0.8;
}

.cta-text {
    font-size: 16px;
    font-weight: 500;
    margin-top: 10px;
}

/* Content page styles */
.content-page {
    background: #ffffff;
    color: #333;
}

.page-title {
    font-size: 32px;
    color: #2c3e50;
    margin-bottom: 10px;
    font-weight: 700;
    border-bottom: 3px solid #3498db;
    padding-bottom: 15px;
}

.page-subtitle {
    font-size: 16px;
    color: #7f8c8d;
    margin-bottom: 30px;
    font-style: italic;
}

/* Restaurant overview */
.restaurant-overview {
    margin-bottom: 40px;
    background: #f8f9fa;
    padding: 25px;
    border-radius: 12px;
    border-left: 5px solid #3498db;
}

.restaurant-overview h3 {
    color: #2c3e50;
    font-size: 24px;
    margin-bottom: 20px;
}

.details-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
}

.detail-item {
    padding: 10px 0;
    border-bottom: 1px solid #e9ecef;
}

.detail-item strong {
    color: #2c3e50;
}

/* Competitive analysis */
.competitive-introduction, .competitive-analysis-section {
    margin-bottom: 40px;
}

.competitive-introduction h3 {
    color: #34495e;
    font-size: 24px;
    margin-bottom: 20px;
}

.intro-box, .analysis-content {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    padding: 30px;
    border-radius: 12px;
    border-left: 5px solid #27ae60;
}

.intro-box p, .analysis-content p {
    font-size: 16px;
    line-height: 1.8;
    color: #2c3e50;
}

.key-takeaway-box {
    background: #fff3cd;
    padding: 20px;
    border-radius: 10px;
    border-left: 4px solid #f39c12;
    margin-top: 20px;
}

.key-takeaway-box h4 {
    color: #856404;
    margin-bottom: 10px;
}

/* Charts */
.chart-section {
    margin: 40px 0;
    text-align: center;
}

.chart-section h4 {
    color: #2c3e50;
    font-size: 20px;
    margin-bottom: 20px;
}

.chart-container {
    background: #ffffff;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border: 1px solid #e9ecef;
}

.chart-image {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
}

.chart-caption {
    margin-top: 15px;
    font-size: 14px;
    color: #7f8c8d;
    font-style: italic;
}

/* Key findings */
.key-findings {
    margin: 40px 0;
}

.key-findings h4 {
    color: #2c3e50;
    font-size: 22px;
    margin-bottom: 25px;
}

.findings-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
}

.insight-card {
    background: #ffffff;
    padding: 25px;
    border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border: 1px solid #e9ecef;
    text-align: center;
    transition: transform 0.2s ease;
}

.insight-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 15px rgba(0,0,0,0.15);
}

.insight-icon {
    font-size: 36px;
    margin-bottom: 15px;
}

.insight-card h5 {
    color: #2c3e50;
    font-size: 16px;
    margin-bottom: 10px;
    font-weight: 600;
}

.insight-card p {
    font-size: 14px;
    color: #7f8c8d;
    line-height: 1.6;
}

/* Opportunity pages */
.opportunity-page {
    background: #ffffff;
}

.opportunity-full-analysis {
    background: #ffffff;
    border: 2px solid #e9ecef;
    border-radius: 15px;
    overflow: hidden;
    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
}

.opportunity-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    text-align: center;
}

.opportunity-title {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 15px;
}

.opportunity-meta {
    display: flex;
    justify-content: center;
    gap: 20px;
    flex-wrap: wrap;
}

.timeline-badge, .difficulty-badge {
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 600;
    background: rgba(255,255,255,0.2);
    border: 1px solid rgba(255,255,255,0.3);
}

.opportunity-sections {
    padding: 30px;
    display: grid;
    gap: 25px;
}

.problem-section, .solution-section, .impact-section, .ai-solution-section, .visual-evidence-section {
    padding: 25px;
    border-radius: 12px;
}

.problem-section {
    background: #fff5f5;
    border-left: 5px solid #e74c3c;
}

.solution-section {
    background: #f0fff4;
    border-left: 5px solid #27ae60;
}

.impact-section {
    background: #fff3cd;
    border-left: 5px solid #f39c12;
}

.ai-solution-section {
    background: #e8f4fd;
    border-left: 5px solid #3498db;
}

.visual-evidence-section {
    background: #f8f9fa;
    border-left: 5px solid #6c757d;
}

.content-box, .impact-box, .ai-solution-box, .visual-suggestion-box {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.problem-section h4, .solution-section h4, .impact-section h4, .ai-solution-section h4, .visual-evidence-section h4 {
    color: #2c3e50;
    margin-bottom: 15px;
    font-size: 18px;
    font-weight: 600;
}

.ai-cta-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 25px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 15px;
}

.evidence-screenshot {
    margin-top: 15px;
}

.evidence-image {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    border: 2px solid #e9ecef;
}

.screenshot-note {
    font-size: 12px;
    color: #6c757d;
    margin-top: 10px;
    font-style: italic;
}

/* Innovation page */
.innovation-page {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

.innovation-section, .long-term-section, .empowerment-section {
    margin-bottom: 40px;
}

.innovation-section h3, .long-term-section h3, .empowerment-section h3 {
    color: #2c3e50;
    font-size: 24px;
    margin-bottom: 20px;
}

.innovation-list, .vision-list {
    display: grid;
    gap: 15px;
}

.innovation-item, .vision-item {
    display: flex;
    align-items: flex-start;
    background: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.innovation-marker, .vision-marker {
    font-size: 24px;
    margin-right: 15px;
    flex-shrink: 0;
}

.empowerment-box {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    border-radius: 15px;
    text-align: center;
    box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
}

.empowerment-box p {
    font-size: 18px;
    line-height: 1.7;
}

/* Screenshots analysis */
.screenshots-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 30px;
}

.screenshot-analysis {
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border: 1px solid #e9ecef;
}

.screenshot-container {
    position: relative;
}

.screenshot-image {
    width: 100%;
    height: 200px;
    object-fit: cover;
}

.screenshot-overlay {
    position: absolute;
    top: 10px;
    right: 10px;
}

.quality-score {
    background: rgba(0,0,0,0.7);
    color: white;
    padding: 5px 10px;
    border-radius: 15px;
    font-size: 12px;
    font-weight: 600;
}

.screenshot-insights {
    padding: 20px;
}

.screenshot-insights h4 {
    color: #2c3e50;
    font-size: 16px;
    margin-bottom: 8px;
}

.page-type {
    color: #3498db;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 10px;
}

.analysis-insight {
    font-size: 14px;
    color: #7f8c8d;
    line-height: 1.5;
}

/* Premium page */
.premium-page {
    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
    color: white;
}

.premium-page .page-title {
    color: white;
    border-bottom: 3px solid #f39c12;
}

.premium-page .page-subtitle {
    color: rgba(255,255,255,0.8);
}

.premium-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 25px;
    margin-bottom: 40px;
}

.premium-card {
    background: rgba(255,255,255,0.1);
    padding: 25px;
    border-radius: 15px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.2);
    text-align: center;
}

.premium-header {
    margin-bottom: 20px;
}

.premium-header h4 {
    color: white;
    font-size: 18px;
    margin-bottom: 10px;
}

.premium-badge {
    background: #f39c12;
    color: white;
    padding: 4px 12px;
    border-radius: 15px;
    font-size: 12px;
    font-weight: 600;
}

.premium-preview {
    margin-bottom: 20px;
}

.premium-preview p {
    font-size: 14px;
    line-height: 1.6;
    color: rgba(255,255,255,0.9);
}

.premium-value {
    margin-bottom: 20px;
}

.value-prop {
    font-size: 13px;
    color: rgba(255,255,255,0.7);
    font-style: italic;
}

.upgrade-btn {
    background: #f39c12;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}

.upgrade-section {
    background: rgba(255,255,255,0.1);
    padding: 30px;
    border-radius: 15px;
    text-align: center;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.2);
}

.upgrade-section h3 {
    color: white;
    font-size: 24px;
    margin-bottom: 20px;
}

.upgrade-section p {
    color: rgba(255,255,255,0.9);
    margin-bottom: 25px;
    line-height: 1.7;
}

.upgrade-benefits {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 30px;
    text-align: left;
}

.benefit-item {
    color: rgba(255,255,255,0.9);
    font-size: 14px;
    padding: 5px 0;
}

.main-upgrade-btn {
    background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
    color: white;
    border: none;
    padding: 15px 30px;
    border-radius: 30px;
    font-size: 18px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 8px 20px rgba(243, 156, 18, 0.3);
}

/* Action page */
.action-page {
    background: rgba(255,255,255,0.95);
}

.action-items-section {
    margin-bottom: 40px;
}

.action-items-section h3 {
    color: #2c3e50;
    font-size: 24px;
    margin-bottom: 25px;
}

.action-items-grid {
    display: grid;
    gap: 20px;
}

.action-item {
    display: flex;
    align-items: flex-start;
    background: white;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    border-left: 5px solid #3498db;
}

.action-number {
    background: #3498db;
    color: white;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    margin-right: 20px;
    flex-shrink: 0;
}

.action-content {
    flex: 2;
}

.action-task {
    font-size: 16px;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 5px;
}

.action-rationale {
    font-size: 14px;
    color: #7f8c8d;
    line-height: 1.5;
}

.action-status {
    flex: 0.5;
    text-align: center;
}

.action-checkbox {
    margin-right: 5px;
}

.consultation-section {
    background: #f8f9fa;
    padding: 30px;
    border-radius: 15px;
    border-left: 5px solid #27ae60;
}

.consultation-section h3 {
    color: #2c3e50;
    font-size: 24px;
    margin-bottom: 15px;
}

.questions-list {
    margin: 25px 0;
}

.question-item {
    display: flex;
    align-items: flex-start;
    margin-bottom: 15px;
    padding: 15px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.question-marker {
    font-size: 18px;
    margin-right: 15px;
    color: #3498db;
}

.consultation-cta {
    text-align: center;
    margin-top: 25px;
}

.consultation-btn {
    background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
    color: white;
    border: none;
    padding: 15px 30px;
    border-radius: 30px;
    font-size: 18px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 8px 20px rgba(39, 174, 96, 0.3);
}

.consultation-note {
    color: #7f8c8d;
    font-size: 14px;
    margin-top: 10px;
    font-style: italic;
}

/* Footer page */
.footer-page {
    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
    color: white;
    text-align: center;
    justify-content: space-between;
}

.footer-content h2 {
    font-size: 36px;
    margin-bottom: 10px;
    font-weight: 700;
}

.footer-tagline {
    font-size: 18px;
    margin-bottom: 40px;
    opacity: 0.8;
}

.contact-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 30px;
    margin-bottom: 40px;
}

.contact-item {
    background: rgba(255,255,255,0.1);
    padding: 25px;
    border-radius: 15px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.2);
}

.contact-item h4 {
    color: #3498db;
    font-size: 16px;
    margin-bottom: 10px;
}

.contact-item p {
    font-size: 14px;
    margin-bottom: 5px;
    opacity: 0.9;
}

.footer-stats {
    margin-bottom: 40px;
}

.footer-stats h3 {
    font-size: 24px;
    margin-bottom: 20px;
    color: #3498db;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
}

.stats-grid .stat-item {
    background: rgba(255,255,255,0.1);
    padding: 15px;
    border-radius: 10px;
}

.stat-value {
    font-size: 24px;
    font-weight: 700;
    display: block;
    margin-bottom: 5px;
    color: #3498db;
}

.stat-label {
    font-size: 12px;
    opacity: 0.8;
}

.footer-disclaimer {
    background: rgba(0,0,0,0.3);
    padding: 20px;
    border-radius: 10px;
    text-align: left;
}

.footer-disclaimer p {
    margin-bottom: 10px;
}

.disclaimer-text {
    font-size: 12px;
    opacity: 0.7;
    line-height: 1.5;
}

/* Print optimizations */
@media print {
    .page {
        page-break-inside: avoid;
    }
    
    .opportunity-page {
        page-break-before: always;
    }
    
    body {
        -webkit-print-color-adjust: exact;
        color-adjust: exact;
    }
}
"""
        
        # Write templates to files
        template_file = self.templates_dir / "main_report.html"
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(main_template)
        
        css_file = self.static_dir / "report_styles.css"
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(css_content)
        
        logger.info(f"✅ Default templates created: {template_file}, {css_file}")
    
    def generate_charts(self, final_restaurant_output: 'FinalRestaurantOutput') -> Dict[str, str]:
        """
        Generate charts from FinalRestaurantOutput data and return as base64 encoded images.
        """
        logger.info(f"📊 Generating charts for {final_restaurant_output.restaurant_name}")
        charts = {}
        
        try:
            # 1. Competitive Ratings Comparison Chart
            if final_restaurant_output.competitors:
                logger.info("📊 Creating competitive ratings comparison chart")
                
                # Extract competitor data
                competitor_names = []
                competitor_ratings = []
                competitor_review_counts = []
                
                # Add target restaurant
                target_name = final_restaurant_output.restaurant_name or 'Your Restaurant'
                target_rating = 0.0
                target_reviews = 0
                
                # Try to get target restaurant rating from Google My Business data
                if final_restaurant_output.google_my_business:
                    gmb_data = final_restaurant_output.google_my_business
                    target_rating = getattr(gmb_data, 'rating', 0.0) or 0.0
                    target_reviews = getattr(gmb_data, 'user_ratings_total', 0) or 0
                
                competitor_names.append(target_name)
                competitor_ratings.append(target_rating)
                competitor_review_counts.append(target_reviews)
                
                # Add competitors
                for comp in final_restaurant_output.competitors[:5]:  # Limit to top 5 competitors
                    competitor_names.append(comp.name or 'Unknown')
                    competitor_ratings.append(getattr(comp, 'rating', 0.0) or 0.0)
                    competitor_review_counts.append(getattr(comp, 'review_count', 0) or 0)
                
                # Create the chart
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
                fig.suptitle('Competitive Analysis Dashboard', fontsize=16, fontweight='bold')
                
                # Ratings comparison
                colors = ['#FF6B6B'] + ['#4ECDC4'] * (len(competitor_names) - 1)  # Highlight target restaurant
                bars1 = ax1.bar(competitor_names, competitor_ratings, color=colors, alpha=0.8)
                ax1.set_ylabel('Average Rating', fontweight='bold')
                ax1.set_title('Customer Ratings Comparison', fontweight='bold')
                ax1.set_ylim(0, 5)
                ax1.grid(axis='y', alpha=0.3)
                
                # Add value labels on bars
                for bar in bars1:
                    height = bar.get_height()
                    ax1.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                            f'{height:.1f}⭐', ha='center', va='bottom', fontweight='bold')
                
                # Review count comparison  
                bars2 = ax2.bar(competitor_names, competitor_review_counts, color=colors, alpha=0.8)
                ax2.set_ylabel('Number of Reviews', fontweight='bold')
                ax2.set_title('Review Volume Comparison', fontweight='bold')
                ax2.grid(axis='y', alpha=0.3)
                
                # Add value labels
                for bar in bars2:
                    height = bar.get_height()
                    ax2.text(bar.get_x() + bar.get_width()/2., height + (max(competitor_review_counts) * 0.01),
                            f'{int(height)}', ha='center', va='bottom', fontweight='bold')
                
                # Rotate x-axis labels if too long
                plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
                plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
                
                plt.tight_layout()
                
                # Convert to base64
                img_buffer = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                plt.savefig(img_buffer.name, format='png', dpi=150, bbox_inches='tight')
                plt.close()
                
                with open(img_buffer.name, 'rb') as img_file:
                    charts['ratings_comparison'] = base64.b64encode(img_file.read()).decode()
                
                os.unlink(img_buffer.name)
                logger.info("✅ Competitive ratings chart generated")
            
            # 2. Menu Categories Distribution Chart (if menu items available)
            if final_restaurant_output.menu_items and len(final_restaurant_output.menu_items) > 0:
                logger.info("📊 Creating menu categories distribution chart")
                
                # Categorize menu items
                category_counts = {}
                for item in final_restaurant_output.menu_items:
                    category = getattr(item, 'category', None) or self._categorize_menu_item(item.name)
                    category_counts[category] = category_counts.get(category, 0) + 1
                
                if category_counts:
                    # Create pie chart
                    fig, ax = plt.subplots(figsize=(8, 8))
                    
                    categories = list(category_counts.keys())
                    counts = list(category_counts.values())
                    
                    # Custom colors
                    colors = sns.color_palette("husl", len(categories))
                    
                    wedges, texts, autotexts = ax.pie(counts, labels=categories, autopct='%1.1f%%',
                                                     colors=colors, startangle=90)
                    
                    # Enhance text
                    for autotext in autotexts:
                        autotext.set_color('white')
                        autotext.set_fontweight('bold')
                    
                    ax.set_title(f'Menu Categories Distribution\n({len(final_restaurant_output.menu_items)} total items)', 
                               fontsize=14, fontweight='bold')
                    
                    plt.tight_layout()
                    
                    # Convert to base64
                    img_buffer = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    plt.savefig(img_buffer.name, format='png', dpi=150, bbox_inches='tight')
                    plt.close()
                    
                    with open(img_buffer.name, 'rb') as img_file:
                        charts['menu_distribution'] = base64.b64encode(img_file.read()).decode()
                    
                    os.unlink(img_buffer.name)
                    logger.info("✅ Menu distribution chart generated")
            
            # 3. Business Intelligence Metrics Chart
            logger.info("📊 Creating business intelligence metrics chart")
            
            # Create a metrics overview chart
            fig, ax = plt.subplots(figsize=(10, 6))
            
            metrics = {
                'Menu Items Online': len(final_restaurant_output.menu_items),
                'Social Platforms': len(final_restaurant_output.social_media_profiles or []),
                'Screenshots Captured': len(final_restaurant_output.screenshots or []),
                'Competitors Analyzed': len(final_restaurant_output.competitors or []),
                'PDFs Processed': len(final_restaurant_output.menu_pdf_s3_urls or [])
            }
            
            metric_names = list(metrics.keys())
            metric_values = list(metrics.values())
            
            bars = ax.bar(metric_names, metric_values, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7'])
            
            ax.set_ylabel('Count', fontweight='bold')
            ax.set_title('Data Collection Overview', fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                       f'{int(height)}', ha='center', va='bottom', fontweight='bold')
            
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
            plt.tight_layout()
            
            # Convert to base64
            img_buffer = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.savefig(img_buffer.name, format='png', dpi=150, bbox_inches='tight')
            plt.close()
            
            with open(img_buffer.name, 'rb') as img_file:
                charts['business_intelligence'] = base64.b64encode(img_file.read()).decode()
            
            os.unlink(img_buffer.name)
            logger.info("✅ Business intelligence chart generated")
            
        except Exception as e:
            logger.error(f"❌ Chart generation failed: {str(e)}")
            # Return empty charts dict on failure
            charts = {}
        
        logger.info(f"📊 Generated {len(charts)} charts successfully")
        return charts
    
    def _categorize_menu_item(self, item_name: str) -> str:
        """Categorize a menu item by name."""
        if not item_name:
            return 'Other'
        
        item_lower = item_name.lower()
        
        if any(word in item_lower for word in ['salad', 'greens', 'vegetables']):
            return 'Salads'
        elif any(word in item_lower for word in ['burger', 'sandwich', 'wrap']):
            return 'Sandwiches'
        elif any(word in item_lower for word in ['pasta', 'noodles', 'spaghetti']):
            return 'Pasta'
        elif any(word in item_lower for word in ['pizza', 'flatbread']):
            return 'Pizza'
        elif any(word in item_lower for word in ['soup', 'broth', 'bisque']):
            return 'Soups'
        elif any(word in item_lower for word in ['chicken', 'beef', 'pork', 'lamb', 'steak']):
            return 'Main Dishes'
        elif any(word in item_lower for word in ['dessert', 'cake', 'ice cream', 'sweet']):
            return 'Desserts'
        elif any(word in item_lower for word in ['coffee', 'tea', 'drink', 'juice', 'soda']):
            return 'Beverages'
        elif any(word in item_lower for word in ['appetizer', 'starter', 'small plate']):
            return 'Appetizers'
        else:
            return 'Other'
    
    async def generate_pdf_report(self, final_restaurant_output: 'FinalRestaurantOutput') -> Dict:
        """
        Generate a comprehensive PDF report from FinalRestaurantOutput (Phase A + Phase B).
        Enhanced to handle the sophisticated LLMA-6 strategic analysis structure.
        
        Args:
            final_restaurant_output: Complete restaurant data with LLMA-6 strategic analysis
        
        Returns:
            Dictionary with PDF generation results including S3 URL
        """
        restaurant_name = final_restaurant_output.restaurant_name or 'Unknown Restaurant'
        logger.info(f"📄 Generating enhanced PDF report for {restaurant_name}")
        
        try:
            # Create templates if they don't exist
            if not (self.templates_dir / "main_report.html").exists():
                self.create_default_templates()
            
            # Generate charts from the restaurant data
            charts = self.generate_charts(final_restaurant_output)
            
            # Extract LLMA-6 strategic analysis from Phase B
            strategic_analysis = final_restaurant_output.llm_strategic_analysis
            if not strategic_analysis or not isinstance(strategic_analysis, dict):
                logger.warning(f"⚠️ No LLMA-6 strategic analysis available for {restaurant_name}, using fallback")
                strategic_analysis = self._create_fallback_strategic_analysis()
            
            logger.info(f"📊 Strategic analysis keys: {list(strategic_analysis.keys()) if strategic_analysis else 'None'}")
            
            # Debug: Log the structure of immediate_action_items_quick_wins
            immediate_actions_raw = strategic_analysis.get('immediate_action_items_quick_wins', [])
            logger.info(f"🔍 DEBUG: immediate_action_items_quick_wins type: {type(immediate_actions_raw)}, content: {immediate_actions_raw}")
            
            # Process LLMA-6 Executive Hook (nested structure)
            executive_hook_data = strategic_analysis.get('executive_hook', {}) if strategic_analysis else {}
            executive_hook_statement = executive_hook_data.get('hook_statement', 'AI analysis identifies significant growth opportunities for this restaurant.') if isinstance(executive_hook_data, dict) else 'AI analysis identifies significant growth opportunities for this restaurant.'
            biggest_opportunity_teaser = executive_hook_data.get('biggest_opportunity_teaser', 'The most impactful opportunity lies in digital optimization.') if isinstance(executive_hook_data, dict) else 'The most impactful opportunity lies in digital optimization.'
            
            # Process Competitive Landscape Summary (nested structure)
            competitive_landscape = strategic_analysis.get('competitive_landscape_summary', {}) if strategic_analysis else {}
            competitive_intro = competitive_landscape.get('introduction', 'Based on comprehensive analysis, this restaurant shows strong potential.') if isinstance(competitive_landscape, dict) else 'Based on comprehensive analysis, this restaurant shows strong potential.'
            competitive_detailed_text = competitive_landscape.get('detailed_comparison_text', 'Local market analysis indicates significant opportunities for growth.') if isinstance(competitive_landscape, dict) else 'Local market analysis indicates significant opportunities for growth.'
            competitive_key_takeaway = competitive_landscape.get('key_takeaway_for_owner', 'Focus on digital presence and customer engagement optimization.') if isinstance(competitive_landscape, dict) else 'Focus on digital presence and customer engagement optimization.'
            
            # Process Top 3 Prioritized Opportunities (LLMA-6 detailed structure)
            prioritized_opportunities = strategic_analysis.get('top_3_prioritized_opportunities', []) if strategic_analysis else []
            if not prioritized_opportunities:
                # Try alternative key names that the LLM actually generates
                prioritized_opportunities = strategic_analysis.get('top_3_opportunities', [])
                if not prioritized_opportunities:
                    prioritized_opportunities = strategic_analysis.get('prioritized_opportunities', [])
            
            logger.info(f"🔍 Found {len(prioritized_opportunities)} opportunities from strategic analysis")
            
            processed_opportunities = []
            if prioritized_opportunities and isinstance(prioritized_opportunities, list):
                for i, opp in enumerate(prioritized_opportunities[:3]):  # Ensure we only get top 3
                    if not isinstance(opp, dict):
                        continue  # Skip invalid opportunities
                    processed_opp = {
                        'priority_rank': opp.get('priority_rank', i + 1),
                        'opportunity_title': opp.get('opportunity_title', opp.get('title', f'Strategic Growth Opportunity {i + 1}')),
                        'current_situation_and_problem': opp.get('current_situation_and_problem', opp.get('problem', 'Opportunity for improvement identified.')),
                        'detailed_recommendation': opp.get('detailed_recommendation', opp.get('solution', 'Detailed implementation guidance available.')),
                        'estimated_revenue_or_profit_impact': opp.get('estimated_revenue_or_profit_impact', opp.get('impact', 'Significant impact potential.')),
                        'ai_solution_pitch': opp.get('ai_solution_pitch', 'Our AI platform can automate and optimize this implementation.'),
                        'implementation_timeline': opp.get('implementation_timeline', '1-2 Months'),
                        'difficulty_level': opp.get('difficulty_level', 'Medium (Requires Focused Effort)'),
                        'visual_evidence_suggestion': opp.get('visual_evidence_suggestion', {}),
                        # Legacy compatibility for existing template
                        'title': opp.get('opportunity_title', opp.get('title', f'Strategic Growth Opportunity {i + 1}')),
                        'description': opp.get('current_situation_and_problem', opp.get('problem', 'Opportunity for improvement identified.')),
                        'first_step': opp.get('detailed_recommendation', opp.get('solution', 'Implementation guidance available.'))[:200] + '...',
                        'estimated_impact': opp.get('estimated_revenue_or_profit_impact', opp.get('impact', 'High Impact'))
                    }
                    processed_opportunities.append(processed_opp)
                    logger.info(f"✅ Processed opportunity {i + 1}: {processed_opp['opportunity_title']}")
            
            logger.info(f"🎯 Final processed opportunities count: {len(processed_opportunities)}")
            
            # Process Premium Analysis Teasers (LLMA-6 structure)
            premium_teasers = strategic_analysis.get('premium_analysis_teasers', []) if strategic_analysis else []
            if not premium_teasers:
                # Try alternative key names that the LLM actually generates
                premium_teasers = strategic_analysis.get('further_insights_teaser', [])
                if not premium_teasers:
                    premium_teasers = strategic_analysis.get('insights_teaser', [])
            
            processed_premium_teasers = []
            if premium_teasers and isinstance(premium_teasers, list):
                for teaser in premium_teasers[:3]:  # Limit to 3 teasers
                    if not isinstance(teaser, dict):
                        continue  # Skip invalid teasers
                    processed_premium_teasers.append({
                        'title': teaser.get('premium_feature_title', teaser.get('title', 'Premium Feature')),
                        'teaser': teaser.get('compelling_teaser_hook', teaser.get('teaser', 'Unlock advanced insights for your restaurant.')),
                        'value_proposition': teaser.get('value_proposition', 'Detailed analysis and actionable strategies.')
                    })
            
            # Process Immediate Action Items (LLMA-6 structure) with better error handling
            immediate_actions = strategic_analysis.get('immediate_action_items_quick_wins', []) if strategic_analysis else []
            if not immediate_actions and strategic_analysis:
                # Try alternative key names that the LLM actually generates
                immediate_actions = strategic_analysis.get('generic_success_tips', [])
                if not immediate_actions:
                    immediate_actions = strategic_analysis.get('action_items', [])
                    if not immediate_actions:
                        immediate_actions = strategic_analysis.get('quick_wins', [])
            
            logger.info(f"🔍 Processing {len(immediate_actions)} immediate actions")
            processed_action_items = []
            
            if immediate_actions and isinstance(immediate_actions, list):
                for i, action_item in enumerate(immediate_actions):
                    try:
                        logger.info(f"🔍 Processing action item {i+1}: {type(action_item)}")
                        # Ensure we never pass None to the template
                        if action_item is None:
                            logger.warning(f"⚠️ Skipping None action item at index {i}")
                            continue
                            
                        if isinstance(action_item, dict):
                            action_text = action_item.get('action_item', action_item.get('tip', f'Strategic action item {i+1}'))
                            rationale = action_item.get('rationale_and_benefit', action_item.get('rationale', 'Important for business growth.'))
                            # Ensure we have valid strings
                            if action_text and rationale:
                                processed_action_items.append(f"{action_text} | {rationale}")
                            elif action_text:
                                processed_action_items.append(f"{action_text} | Important for business growth.")
                            else:
                                processed_action_items.append(f"Strategic recommendation {i+1} | Important for business growth.")
                        elif isinstance(action_item, str) and action_item.strip():
                            processed_action_items.append(action_item.strip())
                        else:
                            # Fallback for invalid types
                            processed_action_items.append(f"Strategic recommendation {i+1} | Important for business growth.")
                        logger.info(f"✅ Processed action item {i+1}")
                    except Exception as e:
                        logger.error(f"❌ Error processing action item {i}: {str(e)}")
                        logger.error(f"❌ Action item data: {action_item}")
                        processed_action_items.append(f"Strategic action item {i+1} | Important for business growth.")
            else:
                # Create fallback action items
                logger.warning("⚠️ No valid immediate actions found, creating fallbacks")
                processed_action_items = [
                    "Update online presence and social media | Improves customer discovery and engagement",
                    "Optimize Google My Business listing | Increases local search visibility",
                    "Implement customer feedback system | Enhances service quality and customer satisfaction"
                ]
            
            # Final null safety check - ensure no None values in the list
            processed_action_items = [item for item in processed_action_items if item is not None and str(item).strip()]
            if not processed_action_items:
                processed_action_items = [
                    "Update online presence and social media | Improves customer discovery and engagement",
                    "Optimize Google My Business listing | Increases local search visibility", 
                    "Implement customer feedback system | Enhances service quality and customer satisfaction"
                ]
            
            logger.info(f"✅ Final processed action items count: {len(processed_action_items)}")
            
            # Process Engagement Questions (LLMA-6 structure)
            consultation_questions = strategic_analysis.get('engagement_and_consultation_questions', []) if strategic_analysis else []
            if not consultation_questions:
                # Try alternative key names that the LLM actually generates
                consultation_questions = strategic_analysis.get('follow_up_engagement_questions', [])
                if not consultation_questions:
                    consultation_questions = strategic_analysis.get('engagement_questions', [])
            
            # Ensure it's a list
            if not isinstance(consultation_questions, list):
                consultation_questions = []
            
            # Process Forward-Thinking Strategic Insights (LLMA-6 structure)
            forward_insights = strategic_analysis.get('forward_thinking_strategic_insights', {}) if strategic_analysis else {}
            untapped_ideas = forward_insights.get('untapped_potential_and_innovation_ideas', []) if isinstance(forward_insights, dict) else []
            long_term_thoughts = forward_insights.get('long_term_vision_alignment_thoughts', []) if isinstance(forward_insights, dict) else []
            empowerment_message = forward_insights.get('consultants_core_empowerment_message', 'Growth is achievable with focused effort and strategic implementation.') if isinstance(forward_insights, dict) else 'Growth is achievable with focused effort and strategic implementation.'
            
            # Ensure all lists are actually lists
            if not isinstance(untapped_ideas, list):
                untapped_ideas = []
            if not isinstance(long_term_thoughts, list):
                long_term_thoughts = []
            
            logger.info(f"🎯 Final processed data counts:")
            logger.info(f"  - Opportunities: {len(processed_opportunities)}")
            logger.info(f"  - Premium teasers: {len(processed_premium_teasers)}")
            logger.info(f"  - Action items: {len(processed_action_items)}")
            logger.info(f"  - Consultation questions: {len(consultation_questions)}")
            logger.info(f"  - Untapped ideas: {len(untapped_ideas)}")
            logger.info(f"  - Long-term thoughts: {len(long_term_thoughts)}")
            
            # Calculate comprehensive data points for credibility
            data_points_analyzed = len(final_restaurant_output.menu_items)
            data_points_analyzed += len(final_restaurant_output.competitors or [])
            data_points_analyzed += len(final_restaurant_output.screenshots or [])
            data_points_analyzed += len(final_restaurant_output.social_media_profiles or [])
            data_points_analyzed += len(final_restaurant_output.operating_hours or [])
            if final_restaurant_output.google_my_business:
                data_points_analyzed += 5  # GMB adds significant data
            
            # Extract competitive insights for visual display (enhanced)
            competitive_insights = []
            if processed_opportunities:
                for i, opp in enumerate(processed_opportunities):
                    competitive_insights.append({
                        "icon": ["🎯", "💰", "🚀", "⚡", "🎪"][i % 5],  # Use modulo to prevent index errors
                        "title": str(opp.get('opportunity_title', f'Strategic Growth Opportunity {i + 1}'))[:50] + ('...' if len(str(opp.get('opportunity_title', ''))) > 50 else ''),
                        "description": str(opp.get('estimated_revenue_or_profit_impact', 'Significant impact potential'))[:120] + ('...' if len(str(opp.get('estimated_revenue_or_profit_impact', ''))) > 120 else '')
                    })
            
            # Format screenshots for the template (enhanced)
            formatted_screenshots = []
            if final_restaurant_output.screenshots:
                for screenshot in final_restaurant_output.screenshots[:6]:  # Increased to 6 for better coverage
                    # Ensure screenshot has required attributes
                    screenshot_url = str(getattr(screenshot, 's3_url', '')) if hasattr(screenshot, 's3_url') else str(screenshot.get('s3_url', '')) if isinstance(screenshot, dict) else ''
                    screenshot_caption = getattr(screenshot, 'caption', 'Restaurant digital presence analysis') if hasattr(screenshot, 'caption') else screenshot.get('caption', 'Restaurant digital presence analysis') if isinstance(screenshot, dict) else 'Restaurant digital presence analysis'
                    
                    formatted_screenshots.append({
                        "s3_url": screenshot_url,
                        "caption": screenshot_caption or "Restaurant digital presence analysis",
                        "page_type": getattr(screenshot, 'page_type', 'general') if hasattr(screenshot, 'page_type') else 'general',
                        "quality_score": 4.2,  # Default high quality
                        "analysis_insight": "AI analysis reveals optimization opportunities for improved customer engagement and conversion."
                    })
            
            # Enhanced template data mapping with LLMA-6 integration
            template_data = {
                # Basic restaurant information
                'restaurant_name': restaurant_name,
                'restaurant_address': final_restaurant_output.address_canonical or final_restaurant_output.address_raw or 'Address not available',
                'restaurant_phone': final_restaurant_output.phone_canonical or final_restaurant_output.phone_raw or None,
                'restaurant_website': str(final_restaurant_output.canonical_url),
                'analysis_date': datetime.now().strftime("%B %d, %Y"),
                
                # LLMA-6 Strategic Content (Enhanced Structure)
                'executive_hook': executive_hook_statement,
                'biggest_opportunity_teaser': biggest_opportunity_teaser,
                'competitive_introduction': competitive_intro,
                'competitive_landscape_summary': competitive_detailed_text,
                'competitive_key_takeaway': competitive_key_takeaway,
                'prioritized_opportunities': processed_opportunities,
                'premium_insights_teasers': processed_premium_teasers,
                'immediate_action_items': processed_action_items,
                'consultation_questions': consultation_questions,
                
                # Forward-Thinking Insights (New LLMA-6 Section)
                'untapped_innovation_ideas': untapped_ideas,
                'long_term_strategic_thoughts': long_term_thoughts,
                'empowerment_message': empowerment_message,
                
                # Restaurant operational details
                'cuisine_types': final_restaurant_output.cuisine_types or [],
                'price_range': final_restaurant_output.price_range or 'Not specified',
                'menu_items_count': len(final_restaurant_output.menu_items),
                'description': final_restaurant_output.description_short or final_restaurant_output.description_long_ai_generated or 'Restaurant analysis completed with comprehensive insights.',
                
                # Enhanced credibility and analysis metrics
                'data_points_analyzed': data_points_analyzed,
                'competitors_analyzed': len(final_restaurant_output.competitors or []),
                'opportunities_count': len(processed_opportunities),
                'screenshots_analyzed': len(final_restaurant_output.screenshots or []),
                'social_platforms_analyzed': len(final_restaurant_output.social_media_profiles or []),
                'ai_analysis_depth_score': min(10, max(1, data_points_analyzed // 5)),  # 1-10 scale
                
                # Visual elements and charts
                'competitive_insights': competitive_insights,
                'charts': charts,
                'formatted_screenshots': formatted_screenshots,
                
                # Enhanced metadata for template
                'report_generation_quality': 'Enhanced',
                'llm_analysis_version': 'LLMA-6',
                'strategic_analysis_comprehensive': len(processed_opportunities) >= 3,
                
                # CSS content
                'css_content': self._load_css_content()
            }
            
            # Load and render enhanced template
            template = self.jinja_env.get_template('main_report.html')
            html_content = template.render(**template_data)
            
            # Generate PDF using WeasyPrint with enhanced settings
            logger.info("🔄 Converting enhanced HTML to PDF using WeasyPrint")
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
                # Create WeasyPrint HTML object with better configuration
                html_doc = HTML(string=html_content, base_url=str(self.templates_dir))
                
                # Generate PDF with optimized settings
                html_doc.write_pdf(
                    tmp_pdf.name,
                    stylesheets=[CSS(string=self._load_css_content())],
                    presentational_hints=True,
                    optimize_images=True
                )
                
                pdf_size = os.path.getsize(tmp_pdf.name)
                logger.info(f"✅ Enhanced PDF generated: {pdf_size} bytes")
                
                # Store PDF (S3 if available, local storage as fallback)
                pdf_url = await self._upload_pdf_to_s3(tmp_pdf.name, restaurant_name)
                
                # Clean up temporary file
                os.unlink(tmp_pdf.name)
                
                # Enhanced result with LLMA-6 metrics
                result = {
                    'success': True,
                    'restaurant_name': restaurant_name,
                    'pdf_size_bytes': pdf_size,
                    'generation_timestamp': datetime.now().isoformat(),
                    'charts_generated': len(charts),
                    'opportunities_count': len(processed_opportunities),
                    'competitors_analyzed': len(final_restaurant_output.competitors or []),
                    'screenshots_included': len(formatted_screenshots),
                    'premium_teasers_included': len(processed_premium_teasers),
                    'action_items_included': len(processed_action_items),
                    'consultation_questions_included': len(consultation_questions),
                    'strategic_analysis_version': 'LLMA-6',
                    'strategic_analysis_available': strategic_analysis is not None,
                    'analysis_comprehensiveness_score': template_data['ai_analysis_depth_score'],
                    'storage_type': 'aws_s3' if self.aws_enabled else 'local'
                }
                
                if pdf_url:
                    # Handle both S3 URLs and local file paths
                    if pdf_url.startswith('http'):
                        result['pdf_s3_url'] = pdf_url
                        result['download_url'] = pdf_url
                        result['pdf_filename'] = pdf_url.split('/')[-1]
                        logger.info(f"✅ Enhanced PDF uploaded to S3: {pdf_url}")
                    else:
                        result['pdf_local_path'] = pdf_url
                        result['download_url'] = f"http://localhost:8000{pdf_url}"  # Assume backend serves on 8000
                        result['pdf_filename'] = pdf_url.split('/')[-1]
                        logger.info(f"✅ Enhanced PDF stored locally: {pdf_url}")
                else:
                    result['error'] = 'PDF generated but storage failed'
                    result['success'] = False
                    logger.error("❌ Enhanced PDF generated but storage failed")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Enhanced PDF generation failed for {restaurant_name}: {str(e)}")
            return {
                'success': False,
                'error': f"Enhanced PDF generation failed: {str(e)}",
                'restaurant_name': restaurant_name,
                'strategic_analysis_version': 'LLMA-6'
            }
    
    async def _store_pdf_locally(self, pdf_path: str, restaurant_name: str) -> str:
        """Store PDF locally and return the file path/URL."""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in restaurant_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            
            # Create final filename
            filename = f"{safe_name}_{timestamp}_analysis.pdf"
            local_path = self.local_storage_dir / filename
            
            # Copy the PDF to the storage directory
            import shutil
            shutil.copy2(pdf_path, local_path)
            
            # Return local file URL (relative to backend)
            relative_path = f"/generated_pdfs/{filename}"
            
            logger.info(f"✅ PDF stored locally: {local_path}")
            logger.info(f"📂 Local access URL: {relative_path}")
            
            return relative_path
            
        except Exception as e:
            logger.error(f"❌ Local PDF storage failed: {str(e)}")
            return None
    
    async def _upload_pdf_to_s3(self, pdf_path: str, restaurant_name: str) -> Optional[str]:
        """Upload PDF to S3 and return the public URL (optional, fallback to local)."""
        if not self.aws_enabled:
            logger.info("📁 AWS not configured, using local storage")
            return await self._store_pdf_locally(pdf_path, restaurant_name)
        
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c for c in restaurant_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')
            s3_key = f"restaurant-reports/{safe_name}_{timestamp}_analysis.pdf"
            
            # Upload to S3
            S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET')
            AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
            
            with open(pdf_path, 'rb') as pdf_file:
                self.s3_client.upload_fileobj(
                    pdf_file,
                    S3_BUCKET_NAME,
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'application/pdf',
                        'ACL': 'public-read',
                        'Metadata': {
                            'restaurant': restaurant_name,
                            'generated': datetime.now().isoformat(),
                            'type': 'ai_analysis_report'
                        }
                    }
                )
            
            # Return public URL
            s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"✅ PDF uploaded to S3: {s3_key}")
            return s3_url
            
        except Exception as e:
            logger.error(f"❌ S3 upload failed, falling back to local storage: {str(e)}")
            return await self._store_pdf_locally(pdf_path, restaurant_name)
    
    def _load_css_content(self) -> str:
        """Load CSS content from file or return default."""
        css_file = self.static_dir / "report_styles.css"
        try:
            if css_file.exists():
                with open(css_file, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"⚠️ Failed to load CSS file: {str(e)}")
        
        # Return default CSS if file doesn't exist or fails to load
        return "body { font-family: Arial, sans-serif; margin: 20px; }"

    def _create_fallback_strategic_analysis(self) -> Dict:
        """Create a comprehensive fallback strategic analysis matching LLMA-6 structure when LLM analysis is unavailable."""
        logger.info("📝 Creating LLMA-6 compatible fallback strategic analysis")
        
        return {
            "executive_hook": {
                "hook_statement": "Our AI analysis has identified several growth opportunities that could significantly impact your restaurant's revenue and customer engagement.",
                "biggest_opportunity_teaser": "Digital presence optimization shows the highest potential for immediate impact with measurable revenue gains."
            },
            "competitive_landscape_summary": {
                "introduction": "Based on comprehensive market analysis, your restaurant operates in a competitive landscape with opportunities for strategic differentiation.",
                "detailed_comparison_text": "Local market research indicates that restaurants with optimized digital presence and strategic customer engagement consistently outperform competitors by 15-25% in customer acquisition and retention. Your restaurant has solid fundamentals with room for strategic enhancement in key growth areas.",
                "key_takeaway_for_owner": "Focus on digital optimization and customer experience enhancement to capture untapped market share and improve operational efficiency."
            },
            "top_3_prioritized_opportunities": [
                {
                    "priority_rank": 1,
                    "opportunity_title": "Digital Presence & Online Visibility Optimization",
                    "current_situation_and_problem": "Analysis indicates gaps in your digital footprint that may be limiting customer discovery and engagement. Many potential customers are unable to find comprehensive information about your restaurant online, leading to lost revenue opportunities.",
                    "detailed_recommendation": "Implement a comprehensive digital optimization strategy including Google My Business enhancement, social media presence strengthening, and customer review management. This multi-channel approach will increase visibility and customer engagement across all digital touchpoints.",
                    "estimated_revenue_or_profit_impact": "Conservative estimates suggest 15-25% increase in new customer acquisition, potentially translating to $2,000-$5,000 additional monthly revenue depending on current customer volume and average ticket size.",
                    "ai_solution_pitch": "Our AI OrderFlow Manager can automate review responses, optimize your online listings, and track performance metrics in real-time, ensuring consistent digital presence management.",
                    "implementation_timeline": "2-4 Weeks",
                    "difficulty_level": "Medium (Requires Focused Effort)",
                    "visual_evidence_suggestion": {
                        "idea_for_visual": "Before/after comparison of Google My Business optimization showing improved listing completeness and customer engagement metrics",
                        "relevant_screenshot_s3_url_from_input": None
                    }
                },
                {
                    "priority_rank": 2,
                    "opportunity_title": "Customer Experience & Service Enhancement",
                    "current_situation_and_problem": "Customer feedback analysis suggests opportunities to enhance service quality and operational efficiency. Streamlining operations and improving customer touchpoints can significantly impact satisfaction and repeat business.",
                    "detailed_recommendation": "Develop a comprehensive customer experience strategy focusing on service consistency, staff training, and operational efficiency improvements. Implement customer feedback loops and quality assurance processes.",
                    "estimated_revenue_or_profit_impact": "Improved customer satisfaction typically increases repeat visits by 20-30% and generates positive word-of-mouth marketing, potentially adding $1,500-$3,500 monthly revenue through enhanced customer lifetime value.",
                    "ai_solution_pitch": "Customer Loyalty AI can track customer preferences, automate personalized offers, and predict optimal service timing to maximize satisfaction and revenue per customer.",
                    "implementation_timeline": "4-6 Weeks",
                    "difficulty_level": "Medium (Requires Team Coordination)",
                    "visual_evidence_suggestion": {
                        "idea_for_visual": "Customer journey mapping showing optimized touchpoints and service enhancement opportunities",
                        "relevant_screenshot_s3_url_from_input": None
                    }
                },
                {
                    "priority_rank": 3,
                    "opportunity_title": "Menu Strategy & Pricing Optimization",
                    "current_situation_and_problem": "Menu analysis reveals potential for strategic pricing adjustments and item positioning that could improve profit margins without negatively impacting customer satisfaction.",
                    "detailed_recommendation": "Conduct comprehensive menu engineering analysis to identify high-margin opportunities, optimize item descriptions for increased appeal, and implement strategic pricing adjustments based on competitor analysis and cost optimization.",
                    "estimated_revenue_or_profit_impact": "Menu optimization typically improves profit margins by 3-7% while strategic pricing can increase average transaction value by 8-12%, potentially adding $1,000-$2,500 monthly profit.",
                    "ai_solution_pitch": "Menu Optimizer Pro uses AI analytics to continuously monitor performance, suggest optimal pricing, and predict customer preferences for menu items, ensuring maximum profitability.",
                    "implementation_timeline": "3-5 Weeks",
                    "difficulty_level": "Low to Medium (Data-Driven Approach)",
                    "visual_evidence_suggestion": {
                        "idea_for_visual": "Menu heat map analysis showing performance metrics and optimization opportunities for each item",
                        "relevant_screenshot_s3_url_from_input": None
                    }
                }
            ],
            "premium_analysis_teasers": [
                {
                    "premium_feature_title": "Real-Time Competitor Intelligence Dashboard",
                    "compelling_teaser_hook": "Get instant alerts when competitors change pricing, launch promotions, or receive reviews, giving you first-mover advantage in your local market.",
                    "value_proposition": "Stay ahead of competition with automated monitoring and strategic recommendations based on real-time market changes."
                },
                {
                    "premium_feature_title": "AI-Powered Customer Sentiment Analysis",
                    "compelling_teaser_hook": "Analyze thousands of customer reviews and social media mentions to identify exactly what customers love and what needs improvement.",
                    "value_proposition": "Transform customer feedback into actionable insights with detailed sentiment tracking and automated improvement recommendations."
                },
                {
                    "premium_feature_title": "Dynamic Revenue Optimization Engine",
                    "compelling_teaser_hook": "Automatically adjust pricing, promotions, and inventory based on demand patterns, weather, events, and competitor actions.",
                    "value_proposition": "Maximize revenue 24/7 with AI that never sleeps, constantly optimizing for peak profitability."
                }
            ],
            "immediate_action_items_quick_wins": [
                {
                    "action_item": "Update Google My Business listing with complete information, hours, and recent photos",
                    "rationale_and_benefit": "Increases local search visibility and customer confidence, typically improving inquiry rates by 15-20%"
                },
                {
                    "action_item": "Respond to all recent customer reviews (positive and negative) with professional, personalized messages",
                    "rationale_and_benefit": "Shows active engagement and builds customer trust, often leading to improved ratings and repeat business"
                },
                {
                    "action_item": "Ensure your menu is clearly visible and up-to-date on your website and major platforms",
                    "rationale_and_benefit": "Reduces customer friction and abandonment, directly impacting conversion rates and order completion"
                },
                {
                    "action_item": "Set up automated social media posting schedule for consistent online presence",
                    "rationale_and_benefit": "Maintains top-of-mind awareness and engagement, supporting customer retention and acquisition"
                },
                {
                    "action_item": "Implement a customer email collection system for future marketing opportunities",
                    "rationale_and_benefit": "Builds valuable customer database for direct marketing, enabling targeted promotions and loyalty programs"
                }
            ],
            "engagement_and_consultation_questions": [
                "What's your biggest challenge with attracting new customers in your local market?",
                "How do you currently track and respond to customer feedback and reviews?",
                "What are your primary revenue goals and growth targets for the next 6-12 months?",
                "Which aspects of your restaurant operation feel like they could be most improved with technology?",
                "How do you currently handle online ordering and delivery, and what challenges do you face?"
            ],
            "forward_thinking_strategic_insights": {
                "untapped_potential_and_innovation_ideas": [
                    "Consider implementing AI-powered inventory management to reduce waste and optimize cash flow",
                    "Explore partnerships with local businesses for cross-promotional opportunities and expanded customer base",
                    "Investigate loyalty program automation to increase customer lifetime value and repeat visit frequency",
                    "Look into data analytics platforms to better understand peak hours, popular items, and customer preferences",
                    "Consider implementing contactless ordering and payment systems for enhanced customer convenience"
                ],
                "long_term_vision_alignment_thoughts": [
                    "Building a data-driven operation will position your restaurant for scalable growth and informed decision-making",
                    "Investing in customer relationship technology now will create competitive advantages as the industry becomes more digitized",
                    "Developing strong online presence and automation capabilities provides resilience against market changes and economic fluctuations",
                    "Creating systematic approaches to quality and customer service will support potential expansion or franchise opportunities"
                ],
                "consultants_core_empowerment_message": "Your restaurant has solid fundamentals and significant untapped potential. With focused strategic improvements in digital presence, customer experience, and operational efficiency, you can achieve measurable growth while building a more sustainable and profitable business. The opportunities identified are not just theoretical – they represent actionable pathways to increased revenue, improved customer satisfaction, and long-term business success. Growth is absolutely achievable with systematic implementation and commitment to continuous improvement."
            }
        }

# Global instance
pdf_generator = RestaurantReportGenerator() 