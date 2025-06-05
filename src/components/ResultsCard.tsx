import React from 'react';
import { motion } from 'framer-motion';
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import InsightCard, { InsightCardProps } from '@/components/InsightCard'; // Corrected import path

// Define a more specific type for results data
export interface RestaurantAnalysisResults {
  estimatedSavings: string;
  insights: InsightCardProps[]; // Array of InsightCard props
  competitiveIntel: string[];
}

interface ResultsCardProps {
  data: RestaurantAnalysisResults;
}

const ResultsCard: React.FC<ResultsCardProps> = ({ data }) => {
  console.log('Rendering ResultsCard with data:', data);
  if (!data) {
    console.log('No data provided to ResultsCard, rendering null.');
    return null; 
  }

  return (
    <motion.div
      className="results-card bg-white shadow-2xl rounded-lg p-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-2xl font-bold">AI Analysis Complete</h3>
        {data.estimatedSavings && (
          <Badge className="bg-green-100 text-green-800 py-1 px-3 rounded-full text-lg"> {/* Increased text size */}
            Found ${data.estimatedSavings}/month in opportunities
          </Badge>
        )}
      </div>

      {/* Key Insights */}
      {data.insights && data.insights.length > 0 && (
        <div className="insights-grid grid md:grid-cols-2 gap-6 mb-8">
          {data.insights.map((insight, index) => (
            <InsightCard key={index} {...insight} />
          ))}
        </div>
      )}

      {/* Competitive Intelligence */}
      {data.competitiveIntel && data.competitiveIntel.length > 0 && (
        <div className="competitive-intel mb-8">
          <h4 className="text-lg font-semibold mb-4">Competitive Intelligence</h4>
          <div className="bg-gray-50 p-4 rounded-lg shadow">
            {data.competitiveIntel.map((intel, index) => (
              <p key={index} className="text-sm mb-1">✓ {intel}</p>
            ))}
          </div>
        </div>
      )}

      {/* Call to Action */}
      <div className="cta-section bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6 rounded-lg text-center">
        <h4 className="text-xl font-bold mb-2">
          This is just 5% of what we find with full access
        </h4>
        <p className="mb-4">
          Imagine what we&apos;ll discover when we analyze your actual POS data,
          inventory systems, and internal metrics.
        </p>
        <Button className="bg-white text-blue-600 hover:bg-gray-100 font-semibold py-3 px-6 text-lg"> {/* Enhanced button style */}
          Schedule Your Full AI Consultation →
        </Button>
      </div>
    </motion.div>
  );
};

export default ResultsCard; 