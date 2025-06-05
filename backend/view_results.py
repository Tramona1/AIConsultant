#!/usr/bin/env python3
"""
Simple script to view and evaluate existing restaurant analysis results.

Usage:
    python view_results.py
"""

import json
import os
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET


def load_existing_reports():
    """Load all existing reports from analysis_data directory."""
    analysis_dir = Path("analysis_data")
    
    if not analysis_dir.exists():
        print("❌ No analysis_data directory found.")
        print("💡 Run a restaurant analysis first to generate reports.")
        return []
    
    report_files = list(analysis_dir.glob("*_report.json"))
    
    if not report_files:
        print("❌ No report files found.")
        print("💡 Run a restaurant analysis first to generate reports.")
        return []
    
    reports = []
    
    for report_file in report_files:
        try:
            # Load the JSON report
            with open(report_file, 'r') as f:
                report_data = json.load(f)
            
            # Extract report ID from filename
            report_id = report_file.stem.split('_')[0]
            
            # Try to load corresponding XML analysis
            xml_file = analysis_dir / f"{report_id}_analysis_target.xml"
            xml_content = None
            
            if xml_file.exists():
                with open(xml_file, 'r') as f:
                    xml_content = f.read()
            
            reports.append({
                'id': report_id,
                'data': report_data,
                'xml': xml_content,
                'file_path': report_file
            })
            
        except Exception as e:
            print(f"⚠️ Error loading {report_file}: {str(e)}")
    
    return reports


def display_report_summary(reports):
    """Display a summary of all reports."""
    print("📊 EXISTING ANALYSIS REPORTS")
    print("=" * 60)
    
    for i, report in enumerate(reports, 1):
        data = report['data']
        restaurant_name = data.get('restaurant_name', 'Unknown')
        url = data.get('website_data', {}).get('url', 'Unknown')
        
        # Get basic stats
        reviews = data.get('reviews', {}).get('google', {})
        rating = reviews.get('rating', 'N/A')
        review_count = reviews.get('total_reviews', 'N/A')
        
        competitors = data.get('competitors', {}).get('competitors', [])
        competitor_count = len(competitors)
        
        print(f"{i}. {restaurant_name}")
        print(f"   URL: {url}")
        print(f"   Google Rating: {rating} ({review_count} reviews)")
        print(f"   Competitors Found: {competitor_count}")
        print(f"   Report ID: {report['id']}")
        print(f"   Has Analysis: {'✅' if report['xml'] else '❌'}")
        print()


def display_full_report(report):
    """Display a detailed view of a single report."""
    data = report['data']
    xml_content = report['xml']
    
    print("🏪 RESTAURANT DETAILS")
    print("=" * 50)
    print(f"Name: {data.get('restaurant_name', 'Unknown')}")
    print(f"URL: {data.get('website_data', {}).get('url', 'Unknown')}")
    
    # Contact info
    contact = data.get('website_data', {}).get('contact', {})
    if contact.get('phone'):
        print(f"Phone: {contact['phone']}")
    if contact.get('email'):
        print(f"Email: {contact['email']}")
    
    # Reviews
    reviews = data.get('reviews', {}).get('google', {})
    if reviews:
        print(f"Google Rating: {reviews.get('rating', 'N/A')} ({reviews.get('total_reviews', 'N/A')} reviews)")
    
    # Menu preview
    menu_items = data.get('website_data', {}).get('menu', {}).get('items', [])
    if menu_items:
        print(f"\n🍽️ MENU PREVIEW ({len(menu_items)} items)")
        print("-" * 30)
        for item in menu_items[:5]:  # Show first 5 items
            name = item.get('name', 'Unknown')
            price = item.get('price', 'No price')
            print(f"• {name} - {price}")
        if len(menu_items) > 5:
            print(f"... and {len(menu_items) - 5} more items")
    
    # Competitors
    competitors = data.get('competitors', {}).get('competitors', [])
    if competitors:
        print(f"\n🏢 COMPETITORS ({len(competitors)} found)")
        print("-" * 30)
        for comp in competitors:
            name = comp.get('name', 'Unknown')
            rating = comp.get('rating', 'N/A')
            print(f"• {name} - Rating: {rating}")
    
    # AI Analysis
    if xml_content:
        print(f"\n🤖 AI ANALYSIS")
        print("=" * 50)
        
        # Parse XML to extract insights
        parsed_analysis = parse_xml_simple(xml_content)
        
        if parsed_analysis.get('competitive_landscape'):
            print("🏆 COMPETITIVE LANDSCAPE:")
            for insight in parsed_analysis['competitive_landscape'][:3]:
                print(f"• {insight}")
        
        if parsed_analysis.get('opportunity_gaps'):
            print(f"\n💡 OPPORTUNITY GAPS:")
            for gap in parsed_analysis['opportunity_gaps'][:3]:
                print(f"• {gap}")
        
        if parsed_analysis.get('prioritized_actions'):
            print(f"\n⚡ TOP RECOMMENDATIONS:")
            for action in parsed_analysis['prioritized_actions'][:3]:
                if isinstance(action, dict):
                    print(f"• {action.get('action', str(action))}")
                else:
                    print(f"• {action}")
        
        # Show raw XML preview
        print(f"\n📄 RAW ANALYSIS (first 500 chars)")
        print("-" * 30)
        print(xml_content[:500] + "..." if len(xml_content) > 500 else xml_content)
    
    else:
        print(f"\n❌ No AI analysis found for this report")


def parse_xml_simple(xml_content):
    """Simple XML parser to extract key insights."""
    try:
        # Try to parse as XML first
        root = ET.fromstring(xml_content)
        
        result = {}
        
        # Extract competitive landscape
        comp_elem = root.find('competitive_landscape')
        if comp_elem is not None:
            result['competitive_landscape'] = [item.text for item in comp_elem.findall('item') if item.text]
        
        # Extract opportunity gaps
        opp_elem = root.find('opportunity_gaps')
        if opp_elem is not None:
            result['opportunity_gaps'] = [item.text for item in opp_elem.findall('item') if item.text]
        
        # Extract prioritized actions
        actions_elem = root.find('prioritized_actions')
        if actions_elem is not None:
            actions = []
            for item in actions_elem.findall('action_item'):
                action = item.find('action')
                if action is not None and action.text:
                    actions.append(action.text)
            result['prioritized_actions'] = actions
        
        return result
        
    except ET.ParseError:
        # If XML parsing fails, try to extract text manually
        lines = xml_content.split('\n')
        
        result = {
            'competitive_landscape': [],
            'opportunity_gaps': [],
            'prioritized_actions': []
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if 'competitive_landscape' in line.lower():
                current_section = 'competitive_landscape'
            elif 'opportunity_gaps' in line.lower():
                current_section = 'opportunity_gaps'
            elif 'prioritized_actions' in line.lower():
                current_section = 'prioritized_actions'
            elif line.startswith('•') or line.startswith('-') or line.startswith('1.'):
                if current_section and line:
                    clean_line = line.lstrip('•-1234567890. ').strip()
                    if clean_line:
                        result[current_section].append(clean_line)
        
        return result


def evaluate_report_quality(report):
    """Simple quality evaluation of a report."""
    data = report['data']
    xml_content = report['xml']
    
    if not xml_content:
        print("❌ No analysis to evaluate")
        return
    
    print("🔍 QUALITY EVALUATION")
    print("=" * 40)
    
    # Basic metrics
    word_count = len(xml_content.split())
    print(f"📝 Analysis Length: {word_count} words")
    
    # Check for specific content
    has_competitors = 'competitor' in xml_content.lower()
    has_numbers = any(char.isdigit() for char in xml_content)
    has_recommendations = any(word in xml_content.lower() for word in ['recommend', 'suggest', 'should', 'implement'])
    
    print(f"🏢 Mentions Competitors: {'✅' if has_competitors else '❌'}")
    print(f"📊 Contains Numbers/Data: {'✅' if has_numbers else '❌'}")
    print(f"💡 Has Recommendations: {'✅' if has_recommendations else '❌'}")
    
    # Parse and count sections
    parsed = parse_xml_simple(xml_content)
    
    comp_count = len(parsed.get('competitive_landscape', []))
    opp_count = len(parsed.get('opportunity_gaps', []))
    action_count = len(parsed.get('prioritized_actions', []))
    
    print(f"🏆 Competitive Insights: {comp_count}")
    print(f"💡 Opportunity Gaps: {opp_count}")
    print(f"⚡ Action Items: {action_count}")
    
    # Simple quality score
    quality_factors = [
        word_count >= 200,  # Sufficient length
        has_competitors,    # Mentions competition
        has_numbers,        # Contains data
        has_recommendations, # Has actionable advice
        comp_count >= 2,    # Multiple competitive insights
        opp_count >= 3,     # Multiple opportunities
        action_count >= 2   # Multiple actions
    ]
    
    quality_score = sum(quality_factors) / len(quality_factors) * 10
    
    print(f"\n🎯 Quality Score: {quality_score:.1f}/10")
    
    if quality_score < 5:
        print("💭 Suggestions: Add more specific data, competitor analysis, and actionable recommendations")
    elif quality_score < 7:
        print("💭 Suggestions: Include more specific metrics and detailed competitive insights")
    else:
        print("💭 Good quality analysis! Consider adding more specific dollar amounts or percentages")


def main():
    print("🔍 Restaurant Analysis Results Viewer")
    print("=" * 60)
    
    # Load existing reports
    reports = load_existing_reports()
    
    if not reports:
        return
    
    while True:
        print(f"\nFound {len(reports)} reports:")
        display_report_summary(reports)
        
        print("Options:")
        print("1-{}: View detailed report".format(len(reports)))
        print("q: Quit")
        
        choice = input("\nEnter your choice: ").strip().lower()
        
        if choice == 'q':
            print("👋 Goodbye!")
            break
        
        try:
            report_num = int(choice)
            if 1 <= report_num <= len(reports):
                selected_report = reports[report_num - 1]
                
                print("\n" + "="*80)
                display_full_report(selected_report)
                print("\n" + "="*80)
                evaluate_report_quality(selected_report)
                print("\n" + "="*80)
                
                input("\nPress Enter to continue...")
            else:
                print("❌ Invalid selection")
        except ValueError:
            print("❌ Please enter a number or 'q'")


if __name__ == "__main__":
    main() 