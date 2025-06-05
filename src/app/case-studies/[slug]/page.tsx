'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { Button } from "@/components/ui/button";
import Link from 'next/link';
import { ArrowLeft, Zap, BarChart3, Lightbulb, TrendingUp, TrendingDown, Settings, UserCheck, Clock, DollarSign, Building, Coffee, Smile, Award as AwardIcon, Users, Megaphone, Star } from 'lucide-react';

// Define a type for our case study content
interface CaseStudyContent {
  restaurantName: string;
  location: string;
  slug: string;
  tagline: string;
  icon?: React.ReactNode; // Optional: if we want a specific icon for the study itself
  challenge: {
    title: string;
    narrative: React.ReactNode; // Allows for JSX like <p> and <strong>
  };
  solution: {
    title: string;
    narrative: React.ReactNode;
    points?: { title: string; description: string; icon?: React.ReactNode }[];
  };
  results: {
    title: string;
    narrative: React.ReactNode;
    metrics: { value: string; label: string; icon?: React.ReactNode }[];
    quote?: { text: string; author: string };
  };
}

// Store the detailed case study data
const caseStudiesData: { [key: string]: CaseStudyContent } = {
  'mikes-pizza': {
    restaurantName: "Mike's Pizza",
    location: "Chicago",
    slug: "mikes-pizza",
    tagline: "Slicing Through Hidden Costs with AI",
    icon: <Coffee className="h-10 w-10 text-orange-500" />, 
    challenge: {
      title: "The Mystery of the Disappearing Margins",
      narrative: (
        <>
          <p className="mb-3">Mike&apos;s Pizza, a beloved Chicago neighborhood pizzeria famed for its deep-dish and classic thin-crust pies, was facing a silent threat. Owner Mike Thompson noticed his profit margins were steadily shrinking over six months, despite consistent sales and busy weekend rushes.</p>
          <p className="mb-3">He&apos;d manually reviewed invoices and sales reports but couldn&apos;t pinpoint the exact culprits. &ldquo;We were busy, the ovens were always on, but the numbers just weren&apos;t adding up like they used to,&rdquo; Mike explained. &ldquo;I was losing sleep, wondering if we had a major theft problem or if ingredient prices had just gone through the roof without me noticing every little change.&rdquo;</p>
          <p>The fear was that if this trend continued, he might have to raise prices significantly, potentially alienating his loyal customer base, or worse, cut staff hours.</p>
        </>
      ),
    },
    solution: {
      title: "Illuminating the Cost Culprits with AI",
      narrative: <p className="mb-4">Upon integrating with Mike&apos;s POS and supplier data (with his permission for a deeper analysis), our AI platform began its work:</p>,
      points: [
        { title: "Supplier Invoice Analysis & Price Trend Detection", description: "The AI meticulously scanned months of supplier invoices, flagging incremental price increases from their primary cheese supplier that cumulatively reached an 18% annual hike.", icon: <DollarSign className="h-5 w-5 text-blue-500"/> },
        { title: "Waste & Portioning Anomaly Detection", description: "Cross-referencing inventory usage against sales data, the AI identified that the 'Mega Meat' pizza consistently used 15-20% more mozzarella than specified, pointing to over-portioning.", icon: <BarChart3 className="h-5 w-5 text-blue-500"/> },
        { title: "Automated Ordering & Competitor Benchmarking", description: "The AI analyzed ordering patterns, highlighting costly rush-orders and benchmarked ingredient costs against local averages, revealing his cheese was 8% above median.", icon: <Settings className="h-5 w-5 text-blue-500"/> },
      ],
    },
    results: {
      title: "A Recipe for Renewed Profitability",
      narrative: <p className="mb-4">Armed with these AI-generated insights, Mike took decisive action, including supplier renegotiation, smart portion control, and automated reordering.</p>,
      metrics: [
        { value: "$3,200+", label: "Saved Per Month", icon: <TrendingUp className="h-6 w-6 text-green-500"/> },
        { value: "4% Pts", label: "Margin Recovery on Pizzas", icon: <UserCheck className="h-6 w-6 text-green-500"/> },
        { value: "<1 Hour", label: "Setup Time for Initial Insights", icon: <Clock className="h-6 w-6 text-green-500"/> },
      ],
      quote: {
        text: "The AI didn't just find the problems; it gave us the data to fix them and the tools to prevent them from happening again. It's like having an extra manager who's obsessed with numbers.",
        author: "Mike Thompson, Owner of Mike's Pizza",
      },
    },
  },
  'bellas-bistro': {
    restaurantName: "Bella's Bistro",
    location: "Austin",
    slug: "bellas-bistro",
    tagline: "Turning Midweek Slumps into Revenue Bumps",
    icon: <Smile className="h-10 w-10 text-pink-500" />,
    challenge: {
      title: "The Midweek Ghost Town",
      narrative: (
        <>
          <p className="mb-3">Bella&apos;s Bistro, a charming Italian eatery in Austin, thrived on weekends but faced eerily quiet Tuesdays and Wednesdays. &ldquo;It was like a different restaurant,&rdquo; owner Isabella Rossi sighed. &ldquo;More staff than customers, high food spoilage, and low morale.&rdquo;</p>
          <p>Generic happy hours had little impact, leaving her stuck in a feast-or-famine cycle, worried about the sustainability of her operations during slower parts of the week.</p>
        </>
      ),
    },
    solution: {
      title: "Uncovering Midweek Opportunities with AI",
      narrative: <p className="mb-4">Our AI scanned public data and local market trends for Bella&apos;s Bistro:</p>,
      points: [
        { title: "Competitor Activity Analysis", description: "Identified three nearby competitors running successful, heavily advertised 'Wine Wednesday' or similar promotions, which Bella's general happy hour couldn't match.", icon: <Users className="h-5 w-5 text-blue-500" /> },
        { title: "Social Media Engagement Optimization", description: "Revealed Bella's midweek promotional posts were sporadic and poorly timed, missing the key Sunday-Tuesday planning window, resulting in 60% lower engagement.", icon: <Megaphone className="h-5 w-5 text-blue-500" /> },
        { title: "Dynamic Pricing & Promotion Simulation", description: "Simulated the impact of targeted promotions like a 'Pasta & Pinot Combo', based on competitor success and Bella's menu costs, to maximize appeal.", icon: <Lightbulb className="h-5 w-5 text-blue-500" /> },
      ],
    },
    results: {
      title: "A Lively Midweek and Soaring Sales",
      narrative: <p className="mb-4">Isabella implemented AI-suggested targeted specials, optimized social media, used dynamic pricing for these specials, and even added live music based on AI feedback.</p>,
      metrics: [
        { value: "+40%", label: "Midweek Revenue Increase", icon: <TrendingUp className="h-6 w-6 text-green-500"/> },
        { value: "25%", label: "Increase in Midweek Table Turns", icon: <UserCheck className="h-6 w-6 text-green-500"/> },
        { value: "15%", label: "Reduction in Midweek Food Spoilage", icon: <Zap className="h-6 w-6 text-green-500"/> },
      ],
      quote: {
        text: "The AI gave us a clear roadmap. We weren't just guessing anymore. Our midweek is now something we look forward to!",
        author: "Isabella Rossi, Owner of Bella's Bistro",
      },
    },
  },
  'dragon-palace': {
    restaurantName: "Dragon Palace",
    location: "Seattle",
    slug: "dragon-palace",
    tagline: "Optimizing Schedules, Delighting Diners",
    icon: <AwardIcon className="h-10 w-10 text-red-500" />,
    challenge: {
      title: "The Paradox of High Labor & Low Satisfaction",
      narrative: (
        <>
          <p className="mb-3">Dragon Palace, a popular Seattle Chinese restaurant, faced high labor costs (5-7% above benchmarks) yet suffered from frequent online complaints about &ldquo;slow service&rdquo; and &ldquo;inattentive staff&rdquo; during peak hours. &ldquo;I felt like I was overpaying for underperformance,&rdquo; stated owner Mr. Chen.</p>
          <p>Attempts to add more staff only increased chaos and costs without solving service issues, and his best servers complained about inconsistent earnings on slow shifts.</p>
        </>
      ),
    },
    solution: {
      title: "Aligning Talent with Demand via AI Scheduling Insights",
      narrative: <p className="mb-4">Our AI analyzed Dragon Palace&apos;s POS data (sales volume, order times, table turns) and employee scheduling data:</p>,
      points: [
        { title: "Demand Pattern vs. Staffing Analysis", description: "Identified significant understaffing during crucial 'shoulder peaks' (4:30-5:30 PM takeout, 8:30-9:30 PM weekend dine-in) that were previously overlooked.", icon: <Clock className="h-5 w-5 text-blue-500" /> },
        { title: "Server Performance Correlation", description: "Highlighted that top-performing servers were often on historically slower shifts, while less experienced staff covered chaotic, understaffed peak and shoulder periods.", icon: <Users className="h-5 w-5 text-blue-500" /> },
        { title: "Optimized Scheduling Simulation", description: "Generated alternative scheduling models that reallocated experienced staff to true high-demand times, suggesting staggered starts and flexible shifts.", icon: <Settings className="h-5 w-5 text-blue-500" /> },
      ],
    },
    results: {
      title: "Lower Costs, Happier Customers, Fairer Shifts",
      narrative: <p className="mb-4">Mr. Chen trialed AI-suggested schedules, implemented shift adjustments, and used the AI dashboard for real-time performance monitoring.</p>,
      metrics: [
        { value: "15%", label: "Reduction in Labor Costs", icon: <TrendingDown className="h-6 w-6 text-green-500"/> },
        { value: "+0.8 Stars", label: "Improvement in Service Review Scores (avg)", icon: <Star className="h-6 w-6 text-green-500"/> },
        { value: "12 Mins", label: "Decrease in Peak Order-to-Delivery Times", icon: <Zap className="h-6 w-6 text-green-500"/> },
      ],
      quote: {
        text: "The AI showed us we weren't just understaffed at the wrong times, but we were also underutilizing our best people. Costs are down, and my customers – and my team – are much happier.",
        author: "Mr. Chen, Owner of Dragon Palace",
      },
    },
  },
};


export default function CaseStudyPage() {
  const params = useParams();
  const slug = params?.slug as string || 'unknown-case-study';
  const study = caseStudiesData[slug];

  console.log(`Rendering CaseStudyPage for slug: ${slug}, Found study: ${!!study}`);

  if (!study) {
    return (
      <main className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center">
          <Link href="/">
            <Button variant="outline" className="text-sm mb-8">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Home
            </Button>
          </Link>
          <h1 className="text-4xl font-bold text-gray-800 mb-4">Case Study Not Found</h1>
          <p className="text-lg text-gray-600">Sorry, we couldn&apos;t find the case study you were looking for.</p>
          <Building className="h-32 w-32 text-gray-300 mx-auto my-10" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 py-8 sm:py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <Link href="/#real-examples-section"> 
            <Button variant="outline" className="text-sm hover:bg-gray-100">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to All Examples
            </Button>
          </Link>
        </div>
        
        <article className="bg-white shadow-2xl rounded-xl overflow-hidden">
          <header className="bg-gradient-to-r from-blue-600 to-purple-600 p-6 sm:p-8 text-white">
            {study.icon && <div className="mb-3">{study.icon}</div>}
            <h1 className="text-3xl sm:text-4xl font-bold leading-tight">
              Case Study: {study.restaurantName}
            </h1>
            <p className="mt-2 text-lg text-blue-100">
              {study.tagline}
            </p>
          </header>

          <div className="p-6 sm:p-8 md:p-10 prose prose-lg max-w-none mx-auto text-gray-700">
            
            <section className="mb-10">
              <h2 className="text-2xl font-semibold text-gray-800 mb-3 flex items-center">
                <Zap className="h-6 w-6 mr-3 text-red-500" /> {study.challenge.title}
              </h2>
              <div className="pl-9 text-gray-600 text-base space-y-3">
                {study.challenge.narrative}
              </div>
            </section>
            
            <section className="mb-10">
              <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center">
                <Lightbulb className="h-6 w-6 mr-3 text-yellow-500" /> {study.solution.title}
              </h2>
              <div className="pl-9 text-gray-600 text-base space-y-3">
                {study.solution.narrative}
                {study.solution.points && (
                  <ul className="mt-4 space-y-3 list-none pl-0">
                    {study.solution.points.map((point, index) => (
                      <li key={index} className="flex items-start p-3 bg-blue-50/50 rounded-lg border border-blue-100">
                        {point.icon || <Zap className="h-6 w-6 mr-3 mt-1 text-blue-500 flex-shrink-0" />}
                        <div>
                          <h4 className="font-semibold text-blue-700">{point.title}</h4>
                          <p className="text-sm text-gray-600">{point.description}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
            
            <section className="mb-6">
              <h2 className="text-2xl font-semibold text-gray-800 mb-4 flex items-center">
                 <TrendingUp className="h-6 w-6 mr-3 text-green-500" /> {study.results.title}
              </h2>
              <div className="pl-9 text-gray-600 text-base space-y-3">
                 {study.results.narrative}
              </div>
              <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-center pl-9">
                {study.results.metrics.map((metric, index) => (
                  <div key={index} className="bg-green-50 p-4 rounded-lg shadow-sm border border-green-200">
                    {metric.icon || <BarChart3 className="h-8 w-8 mx-auto mb-2 text-green-600" />}
                    <p className="text-2xl font-bold text-green-700">{metric.value}</p>
                    <p className="text-sm text-gray-600">{metric.label}</p>
                  </div>
                ))}
              </div>
              {study.results.quote && (
                <blockquote className="mt-8 pl-4 italic border-l-4 border-gray-300 text-gray-600 bg-gray-50 p-4 rounded-r-lg">
                  <p className="mb-2"> &ldquo;{study.results.quote.text}&rdquo;</p>
                  <footer className="text-sm font-semibold text-gray-700 text-right">- {study.results.quote.author}</footer>
                </blockquote>
              )}
            </section>

            <div className="mt-12 text-center border-t border-gray-200 pt-10">
                <p className="text-gray-600 mb-4 text-lg">Ready to see how AI can transform your restaurant like {study.restaurantName}?</p>
                <Link href="/#deep-dive-insights">
                     <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 text-base">
                        Explore Our Interactive AI Tools
                    </Button>
                </Link>
            </div>
          </div>
        </article>
      </div>
    </main>
  );
} 