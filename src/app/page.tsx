'use client'; // Required for useState and Framer Motion components

import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { CheckCircle, AlertTriangle, Zap, Clock, TrendingUp, TrendingDown, Settings, Lightbulb, Target, Award, Coffee, Smile, Building, Bot, Star, AlertCircle, ArrowRight, Search, BookOpenText, Megaphone, Sparkles, BrainCircuit, CalendarClock, ArrowRightCircle, ChevronRight, Loader2, ExternalLink } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ResponsiveContainer, BarChart, CartesianGrid, XAxis, YAxis, Tooltip, Bar } from 'recharts';
import Link from 'next/link';

// Placeholder data for sentiment chart
const sentimentData = [
  { category: 'Food Quality', you: 85, competitor: 78 },
  { category: 'Service Speed', you: 70, competitor: 80 },
  { category: 'Ambiance', you: 75, competitor: 72 },
  { category: 'Price Value', you: 60, competitor: 65 },
  { category: 'Cleanliness', you: 90, competitor: 88 },
];

interface RealExampleProps {
  restaurantName: string;
  location: string;
  problem: string;
  aiFound: string[];
  result: string;
  icon?: React.ReactNode;
}

const RealExampleCard: React.FC<RealExampleProps> = ({ restaurantName, location, problem, aiFound, result, icon }) => {
  console.log("Rendering RealExampleCard for:", restaurantName);
  const slug = restaurantName.toLowerCase().replace(/\s+/g, '-').replace(/\'/g, '');

  return (
    <div className="bg-white p-6 rounded-lg shadow-lg border border-gray-200 flex flex-col h-full">
      <div className="flex items-center mb-3">
        {icon || <Building className="h-8 w-8 text-blue-600 mr-3" />}
        <div>
          <h3 className="text-xl font-semibold text-gray-800">{restaurantName}</h3>
          <p className="text-sm text-gray-500">{location}</p>
        </div>
      </div>
      <div className="flex-grow">
        <p className="text-gray-700 mb-1 text-sm"><strong className="font-medium">Problem:</strong> {problem}</p>
        <div className="mb-3">
          <strong className="font-medium text-gray-700 text-sm">AI Found:</strong>
          <ul className="list-disc list-inside text-xs text-gray-600 ml-1 space-y-0.5">
            {aiFound.map((finding, index) => <li key={index}>{finding}</li>)}
          </ul>
        </div>
        <p className="text-green-700 font-semibold bg-green-50 p-2 rounded text-sm"><strong className="font-medium">Result:</strong> {result}</p>
      </div>
      <div className="mt-auto pt-4">
        <Link href={`/case-studies/${slug}`} passHref>
          <Button variant="outline" className="w-full text-blue-600 border-blue-500 hover:bg-blue-50 text-sm">
            View Case Study <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </Link>
      </div>
    </div>
  );
};

export default function Home() {
  const [activeTab, setActiveTab] = useState<'reviews' | 'legal' | 'margins'>('reviews');

  // State for the new Deep Dive Insights section
  const [restaurantUrl, setRestaurantUrl] = useState('');
  const [restaurantEmail, setRestaurantEmail] = useState('');
  const [operationalHeadache, setOperationalHeadache] = useState('');
  const [curiousMenuItem, setCuriousMenuItem] = useState('');
  const [customAiRequest, setCustomAiRequest] = useState('');
  
  const [analysisOutput, setAnalysisOutput] = useState<{
    url?: string;
    headache?: string;
    menuItem?: string;
    custom?: string;
  }>({});
  const [isLoading, setIsLoading] = useState<{
    url?: boolean;
    headache?: boolean;
    menuItem?: boolean;
    custom?: boolean;
  }>({});

  const handleUrlAnalysis = async () => {
    console.log('🔥 handleUrlAnalysis called with URL:', restaurantUrl);
    if (!restaurantUrl) {
      console.log('❌ No URL provided, exiting');
      return;
    }
    
    console.log('🚀 Starting analysis...');
    setIsLoading(prev => ({ ...prev, url: true }));
    setAnalysisOutput(prev => ({ ...prev, url: undefined })); // Clear previous output

    try {
      console.log('📡 Making API call to backend...');
      const response = await fetch('http://127.0.0.1:8000/analyze-restaurant-progressive', { // NEW: Progressive endpoint
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          url: restaurantUrl,  // Fixed: Changed from restaurant_url to url to match backend API
          email: restaurantEmail || 'test@test.com',  // Use provided email or fallback for testing
          restaurant_name: '', // Optional for progressive system
          address: '' // Optional for progressive system
        }),
      });

      console.log('📬 Response received:', response.status, response.statusText);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('📊 Data received:', data);
      
      // Handle progressive system response format
      if (data.error) {
        throw new Error(data.details || data.error);
      }

      // Extract restaurant data from progressive response
      const restaurantData = data.data_extraction?.restaurant_data || {};
      const extractionMeta = data.data_extraction?.extraction_metadata || {};
      
      // Display results for progressive system
      const initialInsights = `🎉 Progressive Analysis Complete for ${restaurantData.name || data.restaurant_name || restaurantUrl}

📊 **Extraction Summary:**
• Strategy: ${extractionMeta.extraction_strategy || 'progressive_4_phase'}
• Phases completed: ${extractionMeta.phases_completed?.join(', ') || data.phases_completed?.join(', ') || 'N/A'}
• Total time: ${extractionMeta.total_duration_seconds ? `${Math.round(extractionMeta.total_duration_seconds)}s` : 'N/A'}
• Total cost: ${extractionMeta.total_cost_usd ? `$${extractionMeta.total_cost_usd.toFixed(4)}` : 'N/A'}

🏪 **Restaurant Data Found:**
• Address: ${restaurantData.address || 'Not found'}
• Phone: ${restaurantData.phone || 'Not found'}
• Menu items: ${restaurantData.menu_items_count || 0} items
• Social media: ${restaurantData.social_platforms_analyzed || 0} profiles
• Quality score: ${extractionMeta.final_quality_score ? `${(extractionMeta.final_quality_score * 100).toFixed(1)}%` : 'N/A'}

🧠 **Strategic Analysis:**
• Opportunities identified: ${data.strategic_analysis?.opportunities_count || 0}
• Analysis available: ${data.strategic_analysis?.available ? 'Yes' : 'No'}

📄 **PDF Report:**
• Status: ${data.pdf_report?.success ? 'Generated successfully' : 'Failed to generate'}
${data.pdf_report?.download_url ? `• Download: ${data.pdf_report.download_url}` : ''}

✨ This analysis used our new 4-phase progressive system for optimal speed and cost efficiency!`;

      setAnalysisOutput(prev => ({ ...prev, url: initialInsights }));
      console.log('✅ Analysis complete and displayed');

    } catch (error: unknown) {
      console.error("❌ Analysis error:", error);
      setAnalysisOutput(prev => ({ ...prev, url: `Error performing analysis: ${(error as Error).message || "Please check your URL and try again."}` }));
    } finally {
      setIsLoading(prev => ({ ...prev, url: false }));
      console.log('🏁 Analysis finished, loading state reset');
    }
  };

  // Placeholder handlers for other cards - to be implemented
  const handleHeadacheAnalysis = async () => {
    if (!operationalHeadache) return;
    setIsLoading(prev => ({ ...prev, headache: true }));
    setAnalysisOutput(prev => ({ ...prev, headache: undefined }));
    console.log(`Simulating analysis for headache: ${operationalHeadache}`);
    await new Promise(resolve => setTimeout(resolve, 2000));
    const simulatedOutput = `AI-Powered Solutions for "${operationalHeadache}":
1. Root Cause Analysis: Reviewing historical sales vs. staffing data to identify understaffed/overstaffed periods.
2. Predictive Modeling: Forecasting peak times for "${operationalHeadache.toLowerCase().includes("slow") ? "demand generation activities" : "staff allocation"}".
3. Automated Recommendations: Suggesting dynamic pricing for slow periods or optimized schedules.`;
    setAnalysisOutput(prev => ({ ...prev, headache: simulatedOutput }));
    setIsLoading(prev => ({ ...prev, headache: false }));
  };

  const handleMenuItemAnalysis = async () => {
    if (!curiousMenuItem) return;
    setIsLoading(prev => ({ ...prev, menuItem: true }));
    setAnalysisOutput(prev => ({ ...prev, menuItem: undefined }));
    console.log(`Simulating analysis for menu item: ${curiousMenuItem}`);
    await new Promise(resolve => setTimeout(resolve, 2200));
    const simulatedOutput = `Menu Item Analysis for "${curiousMenuItem}":
- Public Perception: Positive mentions around 'unique flavor profile', some concerns about 'portion size vs. price'.
- Competitor Pricing: Similar items from competitors (e.g., 'The Gourmet Burger', 'Artisan Sandwich') are priced on average ${Math.floor(Math.random() * 10) + 3}% ${Math.random() > 0.5 ? 'higher' : 'lower'}.
- Opportunity: Highlight 'locally-sourced ingredients' in marketing. Consider a combo deal to improve perceived value.`;
    setAnalysisOutput(prev => ({ ...prev, menuItem: simulatedOutput }));
    setIsLoading(prev => ({ ...prev, menuItem: false }));
  };
  
  const handleCustomRequestScroll = () => {
    // This will scroll to the main CTA (e.g., footer or a specific CTA section if we add one)
    // For now, let's assume it scrolls to the top join waitlist button
    const navButton = document.querySelector('nav button'); // Simplistic selector, make more robust if needed
    navButton?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // Or, if a dedicated CTA section exists with an ID:
    // document.getElementById('final-cta-section')?.scrollIntoView({ behavior: 'smooth' });
    setAnalysisOutput(prev => ({ ...prev, custom: `Let's discuss your idea: "${customAiRequest}"! We'll reach out to schedule a consultation.`}));
    // No loading state for this one as it's a contact trigger
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-between bg-white overflow-x-hidden font-sans text-gray-800">
      {/* Navigation Bar - Can be a separate component later */}
      <nav className="w-full bg-white shadow-md py-3 px-6 md:px-12 flex justify-between items-center sticky top-0 z-50">
        <div className="flex items-center">
          <Bot className="text-blue-600 h-8 w-8 mr-2" />
          <span className="text-xl md:text-2xl font-bold text-gray-800">Restaurant AI Insights</span>
        </div>
        <div className="flex items-center space-x-2">
          {/* <Button variant="ghost" className="text-gray-600 hover:text-blue-600">Login</Button> */}
          <Button className="bg-blue-600 hover:bg-blue-700 text-white" size="sm">Join the waitlist</Button>
        </div>
      </nav>

      {/* Hero Section */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center py-16 md:py-24 px-4 w-full bg-gradient-to-b from-gray-50 to-white"
      >
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-gray-900 leading-tight mb-6">
          Expert level insights, at a fraction of the cost<span className="text-blue-600"></span>
        </h1>
        <p className="text-lg md:text-2xl mt-4 text-gray-700 max-w-3xl mx-auto mb-10">
        The First Ai Consultant. Quickly and cheaply find gaps in your buiness, fix them, and increase the bottom line.

        </p>
        <div className="flex flex-col sm:flex-row gap-4 mt-8 justify-center">
          <Button size="lg" variant="outline" className="text-lg px-8 py-3 border-gray-300 hover:bg-gray-100 text-blue-600 border-blue-500">
            Join the waitlist
          </Button>
        </div>
        <div className="trust-indicators mt-12 flex flex-wrap gap-x-8 gap-y-4 justify-center text-gray-600">
          <div className="flex items-center text-sm md:text-base"><CheckCircle className="h-5 w-5 mr-2 text-green-500" />Expert Level Insights</div>
          <div className="flex items-center text-sm md:text-base"><CheckCircle className="h-5 w-5 mr-2 text-green-500" /> No Upfront Payment</div>
          <div className="flex items-center text-sm md:text-base"><CheckCircle className="h-5 w-5 mr-2 text-green-500" /> The insights needed to transform your business</div>
        </div>
      </motion.section>

      {/* Hero Analysis Form Section */}
      <section className="py-12 md:py-16 w-full bg-white text-center">
        <div className="max-w-2xl mx-auto px-4">
          <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-4">
            Get Your Free Restaurant Analysis
          </h2>
          <p className="text-gray-600 mb-8">
            Enter your restaurant&apos;s website and email to receive personalized AI insights about your business.
          </p>
          
          <div className="bg-gray-50 rounded-2xl p-6 md:p-8 shadow-lg border border-gray-200">
            <div className="space-y-4">
              <div className="text-left">
                <label htmlFor="restaurant-url" className="block text-sm font-medium text-gray-700 mb-2">
                  Restaurant Website URL
                </label>
                <Input
                  id="restaurant-url"
                  type="url"
                  placeholder="https://your-restaurant.com"
                  value={restaurantUrl}
                  onChange={(e) => setRestaurantUrl(e.target.value)}
                  className="w-full text-base"
                />
              </div>
              
              <div className="text-left">
                <label htmlFor="restaurant-email" className="block text-sm font-medium text-gray-700 mb-2">
                  Email Address
                </label>
                <Input
                  id="restaurant-email"
                  type="email"
                  placeholder="owner@your-restaurant.com"
                  value={restaurantEmail}
                  onChange={(e) => setRestaurantEmail(e.target.value)}
                  className="w-full text-base"
                />
              </div>
              
              <Button 
                size="lg" 
                className="w-full bg-blue-600 hover:bg-blue-700 text-white text-lg py-4 shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 ease-in-out"
                onClick={handleUrlAnalysis}
                disabled={!restaurantUrl || isLoading.url}
              >
                {isLoading.url ? (
                  <>🔄 Analyzing...</>
                ) : (
                  'Get Free AI Analysis'
                )}
              </Button>
              
              {!restaurantUrl && (
                <p className="text-xs text-orange-600 mt-2 font-medium">📍 Please enter a restaurant website URL above to enable analysis</p>
              )}
              {restaurantUrl && !restaurantEmail && (
                <p className="text-xs text-blue-600 mt-2">💡 Email is optional - you can analyze without it! Click the button to start.</p>
              )}
              {restaurantUrl && restaurantEmail && (
                <p className="text-xs text-green-600 mt-2 font-medium">✅ Ready to analyze! Click the button above.</p>
              )}
              
              {analysisOutput.url && (
                <div className="mt-6 p-4 bg-white rounded-lg border border-gray-200 text-left">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                    <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
                    Analysis Results
                  </h3>
                  <div className="text-sm text-gray-700 whitespace-pre-wrap">
                    {analysisOutput.url}
                  </div>
                </div>
              )}
              
              <p className="text-xs text-gray-500 mt-4">
                By submitting this form, you agree to receive email communications about your restaurant analysis and potential solutions.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Product Showcase Section */}
      <section className="product-showcase py-12 md:py-20 px-4 w-full">
        <div className="container mx-auto">
          {/* Three clickable insight cards */}
          <div className="insight-tabs flex flex-col sm:flex-row gap-4 mb-8 justify-center">
            <InsightTab
              active={activeTab === 'reviews'}
              onClick={() => setActiveTab('reviews')}
              icon={<Star className="h-5 w-5 mr-2"/>}
              title="Why your competitor has 50 more reviews"
            />
            <InsightTab
              active={activeTab === 'legal'}
              onClick={() => setActiveTab('legal')}
              icon={<AlertTriangle className="h-5 w-5 mr-2"/>}
              title="Legal risks hiding in your operation"
            />
            <InsightTab
              active={activeTab === 'margins'}
              onClick={() => setActiveTab('margins')}
              icon={<TrendingUp className="h-5 w-5 mr-2"/>}
              title="Increase margins by 2% in 60 days"
            />
          </div>

          {/* The actual product interface */}
          <div className="product-interface bg-gray-100 rounded-2xl shadow-2xl p-1 max-w-4xl mx-auto">
            {/* Fake browser chrome */}
            <div className="browser-header bg-slate-200 rounded-t-xl p-3 flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-400"></div>
                <div className="w-3 h-3 rounded-full bg-green-400"></div>
              </div>
              <div className="flex-1 flex justify-center">
                <div className="bg-gray-50 rounded-full px-4 py-1 text-xs sm:text-sm text-gray-600 w-full sm:w-auto max-w-md truncate">
                  https://restaurant-ai.com/dashboard/{activeTab}
                </div>
              </div>
            </div>

            {/* The actual dashboard content */}
            <div className="dashboard-content bg-white p-4 sm:p-6 md:p-8 rounded-b-xl">
              {activeTab === 'reviews' && <ReviewsInsight />}
              {activeTab === 'legal' && <LegalInsight />}
              {activeTab === 'margins' && <MarginsInsight />}
            </div>
          </div>
        </div>
      </section>

      {/* What This Is Section - REVISED */}
      <section className="py-12 md:py-20 px-4 w-full bg-gray-50">
        <div className="max-w-7xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6 text-gray-900">
            Reimagine Your Restaurant Operations with AI
          </h2>
          <p className="text-lg text-gray-600 mb-12 max-w-3xl mx-auto">
            Imagine an expert AI consultant working for your restaurant 24/7. This AI doesn&apos;t just report problems; it actively helps you find opportunities, optimize operations, and automate solutions to boost your bottom line. Here&apos;s how:
          </p>
          <div className="grid md:grid-cols-3 gap-8 text-left">
            {/* Column 1: Uncover Deep Insights */}
            <div className="bg-white p-6 rounded-xl shadow-lg border border-blue-100 hover:shadow-blue-100/50 transition-shadow duration-300">
              <div className="flex items-center mb-5">
                <Lightbulb className="h-10 w-10 text-blue-600 mr-4 flex-shrink-0" />
                <div>
                  <h3 className="text-xl sm:text-2xl font-semibold text-blue-700">Uncover Deep Insights</h3>
                  <p className="text-xs text-blue-500">Find & Understand Critical Information</p>
                </div>
              </div>
              <ul className="space-y-4">
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Monitor Performance & Competitors</h4>
                </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Predict Sales Trends & Prevent Dips</h4>
                </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Analyze Customer Behavior</h4>
                </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Benchmark Against the Best</h4>
                </li>
              </ul>
            </div>

            {/* Column 2: Optimize & Strategize */}
            <div className="bg-white p-6 rounded-xl shadow-lg border border-green-100 hover:shadow-green-100/50 transition-shadow duration-300">
              <div className="flex items-center mb-5">
                <Target className="h-10 w-10 text-green-600 mr-4 flex-shrink-0" />
                 <div>
                  <h3 className="text-xl sm:text-2xl font-semibold text-green-700">Optimize & Strategize</h3>
                  <p className="text-xs text-green-500">Create & Summarize Actionable Plans</p>
                </div>
              </div>
              <ul className="space-y-4">
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Maximize Revenue Streams</h4>
                </li>
                 <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Optimize Menu & Dynamic Pricing</h4>
                </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Enhance Staffing Efficiency</h4>
                </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Reduce Operational Waste</h4>
                </li>
              </ul>
            </div>

            {/* Column 3: Automate & Execute */}
            <div className="bg-white p-6 rounded-xl shadow-lg border border-purple-100 hover:shadow-purple-100/50 transition-shadow duration-300">
              <div className="flex items-center mb-5">
                <Zap className="h-10 w-10 text-purple-600 mr-4 flex-shrink-0" />
                <div>
                  <h3 className="text-xl sm:text-2xl font-semibold text-purple-700">Automate & Execute</h3>
                  <p className="text-xs text-purple-500">Orchestrate Workflows & Implement Fixes</p>
                </div>
              </div>
              <ul className="space-y-4">
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Implement Automated Solutions</h4>
                </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Proactively Prevent Issues & Seize Opportunities</h4>
                </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Streamline Repetitive Tasks</h4>
          </li>
                <li>
                  <h4 className="font-semibold text-gray-800 text-base mb-0.5">Execute Targeted Growth Campaigns</h4>
          </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* New Packages Section */}
      <section className="py-12 md:py-20 px-4 w-full bg-blue-50">
        <div className="max-w-5xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-5 text-gray-900">Choose Your AI-Powered Boost</h2>
          <p className="text-lg text-gray-600 mb-12 max-w-2xl mx-auto">
            Select a focused AI analysis package using publicly available data to target specific areas of your business, or request a custom solution for your unique needs. All priced to deliver immediate value.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
            <PackageCard
              icon={<Search className="h-10 w-10 text-indigo-600 mb-4" />}
              title="Website Evaluation"
              description="AI-driven analysis of your website's user experience, mobile-friendliness, SEO basics, and accessibility, using publicly available information to ensure it's effectively attracting customers."
              price={249}
            />
            <PackageCard
              icon={<BookOpenText className="h-10 w-10 text-rose-600 mb-4" />}
              title="Menu Evaluation"
              description="Leverage AI to analyze your menu's pricing, item descriptions, and perceived value based on publicly available competitor data and online customer discussions."
              price={249}
            />
            <PackageCard
              icon={<Megaphone className="h-10 w-10 text-teal-600 mb-4" />}
              title="Brand Evaluation"
              description="Understand your restaurant's public image. AI analyzes online reviews, social media mentions, and local listings to gauge brand sentiment, visibility, and competitive positioning."
              price={249}
            />
            <PackageCard
              icon={<Sparkles className="h-10 w-10 text-slate-600 mb-4" />}
              title="+ Custom AI Plan"
              description="Have a unique challenge or data-driven question? Describe your needs, and we'll explore how our AI can provide a custom analysis using available data."
              price="custom"
              ctaText="Request Custom Plan"
            />
          </div>
        </div>
      </section>
      
      {/* Real Examples Section */}
      <section className="py-12 md:py-20 px-4 w-full">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-12 text-gray-900">Real Examples from Real Restaurants</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <RealExampleCard 
              restaurantName="Mike's Pizza"
              location="Chicago"
              problem="Food costs creeping up, didn't know why."
              aiFound={["Cheese vendor slowly raising prices", "Prep cook over-portioning."]}
              result="Saved $3,200/month with automated ordering and portion alerts."
              icon={<Coffee className="h-8 w-8 text-orange-500 mr-3"/>}
            />
            <RealExampleCard 
              restaurantName="Bella's Bistro"
              location="Austin"
              problem="Slow Tuesday/Wednesday nights."
              aiFound={["Competitors doing wine specials", "Social media posts timed wrong."]}
              result="+40% midweek revenue with dynamic pricing."
              icon={<Smile className="h-8 w-8 text-pink-500 mr-3"/>}
            />
             <RealExampleCard 
              restaurantName="Dragon Palace"
              location="Seattle"
              problem="High labor costs but still bad service reviews."
              aiFound={["Staff scheduled wrong times", "Best servers working slow shifts."]}
              result="Cut labor 15% AND improved service scores."
              icon={<Award className="h-8 w-8 text-red-500 mr-3"/>}
            />
          </div>
        </div>
      </section>

      {/* What You Get Section - REVISED */}
      <section className="py-12 md:py-20 px-4 w-full bg-white">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-5 text-gray-900">
            What You Get: Deeper Insights, Smarter Actions, Lasting Advantage
          </h2>
          <p className="text-lg text-gray-600 text-center mb-12 max-w-2xl mx-auto">
            Our AI doesn&apos;t just give you data; it provides clear pathways to greater profitability and efficiency, helping you stay ahead.
          </p>
          <div className="grid md:grid-cols-2 gap-8">
            <BenefitHighlightCard
              icon={<BrainCircuit className="h-12 w-12 text-blue-600 mb-4" />}
              title="Uncover Hidden Insights"
              description="Understand daily revenue shifts, identify profit-draining menu items, optimize staffing based on demand, and track competitor pricing strategies."
            />
            <BenefitHighlightCard
              icon={<Bot className="h-12 w-12 text-green-600 mb-4" />}
              title="Automate Intelligent Actions"
              description="Implement dynamic pricing that adjusts to demand, smart scheduling that matches busy times, inventory alerts before you run out, and automated customer win-back campaigns."
            />
            <BenefitHighlightCard
              icon={<Target className="h-12 w-12 text-red-600 mb-4" />}
              title="Sharpen Your Competitive Edge"
              description="Gain daily competitive intelligence, spot emerging market trends before your rivals, and understand your unique positioning to attract more customers."
            />
            <BenefitHighlightCard
              icon={<CalendarClock className="h-12 w-12 text-purple-600 mb-4" />}
              title="Predict & Plan Proactively"
              description="Anticipate slow periods to optimize promotions, forecast demand accurately for better resource allocation, and test new business ideas with AI-driven predictions."
            />
          </div>
        </div>
      </section>
      
      {/* Why Restaurants Love This Section */}
      <section className="py-12 md:py-20 px-4 w-full bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-12 text-gray-900">Why Restaurants Love This</h2>
          <div className="space-y-8">
            {[
              { quote: "It's Like Having a Fortune Teller. The AI told us our Saturday night appetizer sales would drop 3 weeks before it happened because of a new competitor. We adjusted our happy hour and didn't lose a dollar.", author: "Tony, Tony's Steakhouse", icon: <Lightbulb className="text-yellow-500 h-8 w-8 mr-4 flex-shrink-0"/> },
              { quote: "Finally, Answers Not Guesses. I always wondered why our breakfast was struggling. AI showed me we were 20% overpriced compared to the Denny's down the street. Fixed it, breakfast up 35%.", author: "Maria, Sunrise Cafe", icon: <Target className="text-green-500 h-8 w-8 mr-4 flex-shrink-0"/> },
              { quote: "My Margins Went from 3% to 8%! I was ready to close. The AI found $18,000/month in savings I never knew existed. It's like it gave me my life back.", author: "James, The Local Spot", icon: <TrendingUp className="text-blue-500 h-8 w-8 mr-4 flex-shrink-0"/> }
            ].map((testimonial, index) => (
              <div key={index} className="bg-white p-6 rounded-lg shadow-lg flex items-start">
                {testimonial.icon}
                <div>
                  <p className="text-gray-700 italic text-lg mb-3">&quot;{testimonial.quote}&quot;</p>
                  <p className="font-semibold text-gray-800 text-right">- {testimonial.author}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* New Deep Dive Insights Section */}
      <section id="live-demo-section" className="py-16 md:py-24 w-full bg-slate-50">
        <div className="max-w-6xl mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 leading-tight">
              Deep Dive Insights to <span className="text-blue-600">Skyrocket Growth</span>
            </h2>
            <p className="mt-6 text-lg md:text-xl text-gray-600 max-w-3xl mx-auto">
              Unlock actionable intelligence from public data. See how AI can illuminate opportunities and solve challenges for your restaurant in minutes.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 items-start">
            {/* Card 1: Your Restaurant's Public Data Snapshot */}
            <InteractiveInsightCard 
              title="Your Restaurant's Public Data Snapshot"
              icon={<ExternalLink className="h-8 w-8 text-indigo-600" />}
              prompt="Enter Your Restaurant's Website URL (e.g., https://yourpizzaplace.com)"
              inputType="url"
              inputValue={restaurantUrl}
              onInputChange={(e) => setRestaurantUrl(e.target.value)}
              buttonText="Get My Public Data Snapshot"
              onButtonClick={handleUrlAnalysis}
              isLoading={isLoading.url}
              output={analysisOutput.url}
            />

            {/* Card 2: Solve Your #1 Operational Headache */}
            <InteractiveInsightCard 
              title="Solve Your #1 Operational Headache"
              icon={<Lightbulb className="h-8 w-8 text-amber-600" />}
              prompt="What's Your Biggest Operational Challenge Right Now? (e.g., slow Tuesdays, high food waste, staff scheduling)"
              inputType="textarea"
              inputValue={operationalHeadache}
              onInputChange={(e) => setOperationalHeadache(e.target.value)}
              buttonText="See AI-Powered Solutions"
              onButtonClick={handleHeadacheAnalysis}
              isLoading={isLoading.headache}
              output={analysisOutput.headache}
            />

            {/* Card 3: Uncover Menu Item Potential */}
            <InteractiveInsightCard 
              title="Uncover Menu Item Potential"
              icon={<Sparkles className="h-8 w-8 text-rose-600" />}
              prompt="Which Menu Item Are You Most Curious About? (e.g., our new Truffle Burger)"
              inputType="text"
              inputValue={curiousMenuItem}
              onInputChange={(e) => setCuriousMenuItem(e.target.value)}
              buttonText="Analyze This Item (Public Perception & Pricing)"
              onButtonClick={handleMenuItemAnalysis}
              isLoading={isLoading.menuItem}
              output={analysisOutput.menuItem}
            />
            
            {/* Card 4: Design Your Custom AI Project */}
            <InteractiveInsightCard 
              title="Design Your Custom AI Project"
              icon={<Bot className="h-8 w-8 text-teal-600" />}
              prompt="Have a Specific AI Goal or Question? Describe what you want to achieve or analyze, and we'll explore a custom AI solution."
              inputType="textarea"
              inputValue={customAiRequest}
              onInputChange={(e) => setCustomAiRequest(e.target.value)}
              buttonText="Request Custom AI Consultation"
              onButtonClick={handleCustomRequestScroll} // This scrolls, doesn't show loading
              isLoading={false} // No loading for this one
              output={analysisOutput.custom}
            />
          </div>
        </div>
      </section>

      {/* Bottom Line Section */}
      <section className="py-16 md:py-24 px-4 w-full bg-gray-900 text-white">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6">You Work Too Hard to <span className="text-yellow-400">Guess.</span></h2>
          <p className="text-lg text-gray-300 mb-8">
            For less than hiring a dishwasher, get AI that knows your business (almost) better than you do, works 24/7 finding ways to make you more money, helps fix problems automatically, and pays for itself in the first week.
          </p>
          <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-4 mb-10 text-sm">
            <div className="bg-gray-800 p-3 rounded-md flex items-center"><Bot className="h-5 w-5 mr-2 text-blue-400"/> Knows your business</div>
            <div className="bg-gray-800 p-3 rounded-md flex items-center"><Clock className="h-5 w-5 mr-2 text-blue-400"/> Works 24/7</div>
            <div className="bg-gray-800 p-3 rounded-md flex items-center"><Settings className="h-5 w-5 mr-2 text-blue-400"/> Fixes problems</div>
            <div className="bg-gray-800 p-3 rounded-md flex items-center"><Zap className="h-5 w-5 mr-2 text-blue-400"/> Pays for itself fast</div>
          </div>
          <p className="text-2xl font-semibold mb-10">
            The question isn&apos;t &quot;Can I afford this?&quot; <br className="sm:hidden"/> It&apos;s &quot;<span className="text-yellow-400 underline">Can I afford NOT to have this?</span>&quot;
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="bg-green-500 hover:bg-green-600 text-white text-lg font-semibold px-10 py-4">
              Get Started - 30 Minutes to Setup
            </Button>
            <Button size="lg" variant="outline" className="text-lg px-10 py-4 border-gray-400 text-gray-200 hover:bg-gray-700 hover:text-white">
              Questions? Text Us: 555-0123
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="w-full bg-gray-800 text-gray-400 py-10 text-center">
        <div className="mb-2">
            <Bot className="text-blue-500 h-8 w-8 mx-auto mb-1" />
            <p className="text-md font-semibold text-gray-200">Restaurant AI Insights</p>
        </div>
        <p className="text-xs">&copy; {new Date().getFullYear()} AI Restaurant Solutions Inc. All rights reserved.</p>
        <div className="mt-3 space-x-3">
          <a href="/privacy-policy" className="hover:text-white text-xs">Privacy Policy</a>
          <span className="text-gray-600">|</span>
          <a href="/terms-of-service" className="hover:text-white text-xs">Terms of Service</a>
          <span className="text-gray-600">|</span>
          <a href="mailto:hello@restaurantai.insights" className="hover:text-white text-xs">hello@restaurantai.insights</a>
        </div>
      </footer>
      </main>
  );
}

// Helper Components for new Product Showcase section (can be moved to separate files later)

// InsightTab Placeholder
const InsightTab: React.FC<{active: boolean; onClick: () => void; icon: React.ReactNode; title: string}> = ({ active, onClick, icon, title }) => {
  console.log("Rendering InsightTab, title:", title, "Active:", active);
  return (
    <Button
      variant={active ? "default" : "outline"}
      onClick={onClick}
      className={`flex items-center justify-center text-center p-3 sm:p-4 rounded-lg shadow-md transition-all duration-200 ease-in-out w-full sm:w-auto flex-1 
                  ${active ? 'bg-blue-600 text-white scale-105' : 'bg-white text-blue-600 hover:bg-blue-50'}`}
    >
      {icon}
      <span className="text-xs sm:text-sm font-medium">{title}</span>
    </Button>
  );
};

// ReviewsInsight Component
const ReviewsInsight = () => {
  console.log("Rendering ReviewsInsight");
  return (
  <div className="space-y-6">
    <Alert className="border-orange-300 bg-orange-50 text-orange-700">
      <AlertCircle className="h-5 w-5 text-orange-600" />
      <AlertTitle className="font-semibold text-orange-800">Competitive Gap Detected</AlertTitle>
      <AlertDescription className="text-sm">
        Tony&apos;s Pizza (0.3 mi away) has 247 reviews vs your 198. They&apos;re gaining 12 reviews/month while you average 3.
      </AlertDescription>
    </Alert>

    <div className="grid md:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-gray-800">Why They&apos;re Winning</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <CheckCircle className="text-green-500 mt-1 h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-medium text-gray-700">Post-meal review requests</p>
                <p className="text-xs text-gray-500">Automated SMS 2 hours after dining</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="text-green-500 mt-1 h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-medium text-gray-700">Incentivized reviews</p>
                <p className="text-xs text-gray-500">10% off next visit for honest feedback</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="text-green-500 mt-1 h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-medium text-gray-700">QR codes on receipts</p>
                <p className="text-xs text-gray-500">Direct link to Google reviews</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg font-semibold text-gray-800">Your Action Plan</CardTitle>
          <Badge className="bg-green-100 text-green-800 text-xs px-2 py-1">Ready to Deploy</Badge>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Button className="w-full justify-between text-sm py-2">
              Enable Smart Review Requests
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
            <Button variant="outline" className="w-full justify-between text-sm py-2">
              Set Up Receipt QR Codes
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
            <div className="pt-2 text-center">
              <p className="text-xs text-gray-500">Projected outcome:</p>
              <p className="text-xl font-bold text-green-600">+15-20 reviews/month</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold text-gray-800">Sentiment Analysis: You vs Tony&apos;s Pizza</CardTitle>
      </CardHeader>
      <CardContent>
        <div style={{ width: '100%', height: 250 }}> {/* Increased height for better visibility */}
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sentimentData} margin={{ top: 5, right: 20, left: -20, bottom: 5 }}> {/* Adjusted margins */}
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="category" fontSize={10} />
              <YAxis fontSize={10} />
              <Tooltip contentStyle={{fontSize: '12px', padding: '4px 8px'}}/>
              <Bar dataKey="you" fill="#3B82F6" name="Your Restaurant" radius={[4, 4, 0, 0]} barSize={20} />
              <Bar dataKey="competitor" fill="#EF4444" name="Tony's Pizza" radius={[4, 4, 0, 0]} barSize={20} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  </div>
  );
};

// LegalInsight Component
const LegalInsight = () => {
  console.log("Rendering LegalInsight");
  return (
  <div className="space-y-6">
    <Alert className="border-red-300 bg-red-50 text-red-700">
      <AlertTriangle className="h-5 w-5 text-red-600" />
      <AlertTitle className="font-semibold text-red-800">3 Critical Compliance Issues Found</AlertTitle>
      <AlertDescription className="text-sm">
        Immediate action required to avoid potential fines up to $45,000
      </AlertDescription>
    </Alert>

    <div className="grid md:grid-cols-3 gap-4">
      <RiskCard
        severity="high"
        title="ADA Compliance"
        issue="Website missing accessibility features"
        fine="Up to $25,000"
        fix="One-click fix available"
      />
      <RiskCard
        severity="high"
        title="Allergen Labeling"
        issue="Menu missing required allergen info"
        fine="Up to $10,000"
        fix="AI-generated labels ready"
      />
      <RiskCard
        severity="medium"
        title="Employee Records"
        issue="I-9 forms incomplete for 3 employees"
        fine="Up to $2,200 per violation"
        fix="Template provided"
      />
    </div>

    <Card className="bg-gradient-to-r from-blue-50 to-purple-50">
      <CardContent className="p-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-center sm:text-left">
            <h3 className="text-lg font-semibold text-gray-800">Fix All Issues Automatically</h3>
            <p className="text-sm text-gray-600">Our AI has prepared all necessary updates</p>
          </div>
          <Button size="lg" className="bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold w-full sm:w-auto">
            Deploy Fixes Now
          </Button>
        </div>
      </CardContent>
    </Card>
  </div>
  );
};

// MarginsInsight Component
const MarginsInsight = () => {
  console.log("Rendering MarginsInsight");
  return (
  <div className="space-y-6">
    <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-4">
      <MetricCard
        label="Current Margin"
        value="3.2%"
        trend="down"
        change="-0.4%"
      />
      <MetricCard
        label="Industry Average"
        value="5.8%"
        neutral
      />
      <MetricCard
        label="Achievable Target"
        value="5.2%"
        trend="up"
        change="+2%"
      />
      <MetricCard
        label="Monthly Impact"
        value="+$8,400"
        trend="up"
        highlight
      />
    </div>

    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold text-gray-800">Your Path to 5.2% Margins</CardTitle>
        <CardDescription className="text-sm text-gray-500">AI-identified opportunities ranked by impact</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <OpportunityBar
            title="Menu Price Optimization"
            impact="+0.8%"
            effort="Low"
            description="17 items underpriced vs market"
            actionable
          />
          <OpportunityBar
            title="Reduce Food Waste"
            impact="+0.5%"
            effort="Low"
            description="AI predicts daily prep needs"
            actionable
          />
          <OpportunityBar
            title="Smart Labor Scheduling"
            impact="+0.4%"
            effort="Medium"
            description="Match staff to actual demand"
            actionable
          />
          <OpportunityBar
            title="Vendor Negotiation"
            impact="+0.3%"
            effort="Low"
            description="3 vendors charging above market"
            actionable
          />
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold text-gray-800">60-Day Implementation Plan</CardTitle>
      </CardHeader>
      <CardContent>
        <Timeline>
          <TimelineItem
            week="Week 1-2"
            action="Deploy price optimization"
            impact="See +0.8% margin improvement"
          />
          <TimelineItem
            week="Week 3-4"
            action="Launch waste reduction AI"
            impact="Save $2,100 in food costs"
          />
          <TimelineItem
            week="Week 5-6"
            action="Implement smart scheduling"
            impact="Reduce labor costs 12%"
          />
          <TimelineItem
            week="Week 7-8"
            action="Complete vendor renegotiation"
            impact="Lock in 5.2% margins"
          />
        </Timeline>
      </CardContent>
    </Card>
  </div>
  );
};

// RiskCard Placeholder
interface RiskCardProps { severity: "high" | "medium" | "low"; title: string; issue: string; fine: string; fix: string; }
const RiskCard: React.FC<RiskCardProps> = ({ severity, title, issue, fine, fix }) => {
  console.log("Rendering RiskCard, title:", title);
  const severityClasses = {
    high: "border-red-500 bg-red-50",
    medium: "border-yellow-500 bg-yellow-50",
    low: "border-green-500 bg-green-50",
  };
  const severityTextClasses = {
    high: "text-red-700 font-semibold",
    medium: "text-yellow-700 font-semibold",
    low: "text-green-700 font-semibold",
  }
  return (
    <Card className={`shadow-md ${severityClasses[severity]}`}>
      <CardHeader>
        <CardTitle className={`text-md font-semibold ${severityTextClasses[severity]}`}>{title} <span className="uppercase text-xs">({severity})</span></CardTitle>
      </CardHeader>
      <CardContent className="text-xs space-y-1">
        <p><strong className="text-gray-700">Issue:</strong> {issue}</p>
        <p><strong className="text-gray-700">Potential Fine:</strong> {fine}</p>
        <p><strong className="text-gray-700">Suggested Fix:</strong> {fix}</p>
        {fix.toLowerCase().includes("available") || fix.toLowerCase().includes("ready") ? 
          <Button variant="outline" size="sm" className={`mt-2 w-full text-xs ${severity === 'high' ? 'border-red-600 text-red-700 hover:bg-red-100' : 'border-blue-600 text-blue-700 hover:bg-blue-100'}`}>
            {fix.startsWith("One-click") ? "Apply Fix" : "View Details"} <ArrowRight className="h-3 w-3 ml-1"/>
          </Button>
          : null
        }
      </CardContent>
    </Card>
  );
};

// MetricCard Placeholder
interface MetricCardProps { label: string; value: string; trend?: "up" | "down"; change?: string; neutral?: boolean; highlight?: boolean;}
const MetricCard: React.FC<MetricCardProps> = ({ label, value, trend, change, neutral, highlight }) => {
  console.log("Rendering MetricCard, label:", label);
  return (
    <Card className={`p-3 shadow ${highlight ? 'bg-blue-50 border-blue-300' : 'bg-white'}`}>
      <p className="text-xs text-gray-500 truncate">{label}</p>
      <p className={`text-xl font-bold ${highlight ? 'text-blue-600' : 'text-gray-800'}`}>{value}</p>
      {!neutral && trend && change && (
        <p className={`text-xs flex items-center ${trend === 'up' ? 'text-green-600' : 'text-red-600'}`}>
          {trend === 'up' ? <TrendingUp className="h-3 w-3 mr-1"/> : <TrendingDown className="h-3 w-3 mr-1"/> }
          {change}
        </p>
      )}
      {neutral && (<div className="h-4"></div>) /* to maintain height consistency */}
    </Card>
  );
};

// OpportunityBar Placeholder
interface OpportunityBarProps { title: string; impact: string; effort: string; description: string; actionable?: boolean; }
const OpportunityBar: React.FC<OpportunityBarProps> = ({ title, impact, effort, description, actionable }) => {
  console.log("Rendering OpportunityBar, title:", title);
  const effortColors: { [key: string]: string } = {
    Low: "bg-green-100 text-green-700",
    Medium: "bg-yellow-100 text-yellow-700",
    High: "bg-red-100 text-red-700",
  };
  return (
    <div className="p-3 rounded-lg border border-gray-200 bg-gray-50 hover:shadow-md transition-shadow">
      <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-1">
        <h4 className="text-sm font-semibold text-gray-800">{title}</h4>
        <div className="flex items-center gap-2 mt-1 sm:mt-0">
          <Badge variant="secondary" className="text-xs py-0.5 px-1.5">{impact} margin</Badge>
          <Badge variant="outline" className={`text-xs py-0.5 px-1.5 ${effortColors[effort] || 'bg-gray-100 text-gray-700'}`}>{effort} Effort</Badge>
        </div>
      </div>
      <p className="text-xs text-gray-600 mb-2">{description}</p>
      {actionable && (
        <Button variant="link" size="sm" className="p-0 h-auto text-xs text-blue-600 hover:text-blue-700">
          Implement Now <ArrowRight className="h-3 w-3 ml-1" />
        </Button>
      )}
    </div>
  );
};

// Timeline & TimelineItem Placeholders
interface TimelineProps { children: React.ReactNode; }
const Timeline: React.FC<TimelineProps> = ({ children }) => {
  console.log("Rendering Timeline");
  return <div className="space-y-4 relative border-l-2 border-blue-200 pl-6">{children}</div>;
};

interface TimelineItemProps { week: string; action: string; impact: string; }
const TimelineItem: React.FC<TimelineItemProps> = ({ week, action, impact }) => {
  console.log("Rendering TimelineItem, week:", week);
  return (
    <div className="relative">
      <div className="absolute -left-[30px] top-1 h-4 w-4 rounded-full bg-blue-500 border-2 border-white"></div>
      <p className="text-xs font-semibold text-blue-600">{week}</p>
      <h5 className="text-sm font-medium text-gray-700">{action}</h5>
      <p className="text-xs text-gray-500">{impact}</p>
    </div>
  );
};

interface PackageCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  price: number | "custom";
  ctaText?: string;
}

const PackageCard: React.FC<PackageCardProps> = ({ icon, title, description, price, ctaText = "Get Started" }) => {
  console.log("Rendering PackageCard, title:", title);
  return (
    <div className="bg-white p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 flex flex-col text-center items-center border border-gray-200">
      {icon}
      <h3 className="text-xl font-semibold text-gray-800 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 mb-4 flex-grow">{description}</p>
      <div className="mt-auto w-full">
        {price === "custom" ? (
          <p className="text-2xl font-bold text-gray-800 mb-4">Let&apos;s Talk</p>
        ) : (
          <p className="text-2xl font-bold text-gray-800 mb-4">
            ${price}<span className="text-sm font-normal text-gray-500">/mo</span>
          </p>
        )}
        <Button className="w-full bg-blue-600 hover:bg-blue-700 text-white">
          {ctaText}
        </Button>
      </div>
    </div>
  );
};

interface BenefitHighlightCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const BenefitHighlightCard: React.FC<BenefitHighlightCardProps> = ({ icon, title, description }) => {
  console.log("Rendering BenefitHighlightCard, title:", title);
  return (
    <div className="bg-gray-50 p-6 rounded-xl shadow-lg hover:shadow-xl transition-shadow duration-300 flex flex-col items-start h-full border border-gray-200">
      {icon}
      <h3 className="text-xl font-semibold text-gray-800 mb-3">{title}</h3>
      <p className="text-sm text-gray-600 mb-4 flex-grow">{description}</p>
      <div className="mt-auto">
        <ArrowRightCircle className="h-8 w-8 text-gray-400 group-hover:text-blue-500 transition-colors" />
      </div>
    </div>
  );
};

// New InteractiveInsightCard component
interface InteractiveInsightCardProps {
  icon: React.ReactNode;
  title: string;
  prompt: string;
  inputType: "text" | "url" | "textarea";
  inputValue: string;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  buttonText: string;
  onButtonClick: () => void;
  isLoading?: boolean;
  output?: string;
}

const InteractiveInsightCard: React.FC<InteractiveInsightCardProps> = (
  { icon, title, prompt, inputType, inputValue, onInputChange, buttonText, onButtonClick, isLoading, output }
) => {
  console.log(`Rendering InteractiveInsightCard: ${title}, isLoading: ${isLoading}`);
  return (
    <div className="bg-white p-6 rounded-xl shadow-2xl border border-gray-200 flex flex-col min-h-[380px]">
      <div className="flex items-center mb-4">
        {icon}
        <h3 className="ml-3 text-xl font-semibold text-gray-800 leading-tight">{title}</h3>
      </div>
      <p className="text-sm text-gray-600 mb-4 flex-grow min-h-[60px]">{prompt}</p>
      
      {inputType === 'textarea' ? (
        <textarea 
          value={inputValue}
          onChange={onInputChange}
          placeholder="Type here..."
          className="w-full p-3 text-sm border border-gray-300 rounded-md mb-4 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[80px] resize-none"
          rows={3}
          disabled={isLoading}
        />
      ) : (
        <Input 
          type={inputType}
          value={inputValue}
          onChange={onInputChange}
          placeholder={inputType === 'url' ? "https://example.com" : "Type here..."}
          className="w-full p-3 text-sm border-gray-300 rounded-md mb-4 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          disabled={isLoading}
        />
      )}

      <Button 
        onClick={onButtonClick} 
        disabled={isLoading || !inputValue.trim()}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-md transition-all duration-200 ease-in-out disabled:opacity-60 flex items-center justify-center text-sm"
      >
        {isLoading ? (
          <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Analyzing...</>
        ) : (
          <>{buttonText} <ChevronRight className="h-4 w-4 ml-1" /></>
        )}
      </Button>
      {output && (
        <div className="mt-5 pt-4 border-t border-gray-200">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">AI Insights:</h4>
          <pre className="bg-gray-100 p-3 rounded-md text-xs text-gray-700 whitespace-pre-wrap font-mono max-h-48 overflow-y-auto">{output}</pre>
        </div>
      )}
    </div>
  );
};
