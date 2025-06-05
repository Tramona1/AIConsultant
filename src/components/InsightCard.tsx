import React from 'react';
import { motion } from 'framer-motion';

export interface InsightCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  savings?: string;
  impact?: string;
  severity: 'high' | 'medium' | 'low';
}

const InsightCard: React.FC<InsightCardProps> = ({ icon, title, description, savings, impact, severity }) => {
  console.log('Rendering InsightCard with title:', title);
  const severityClasses = {
    high: 'border-red-500 bg-red-50',
    medium: 'border-yellow-500 bg-yellow-50',
    low: 'border-green-500 bg-green-50',
  };

  const severityTextClasses = {
    high: 'text-red-700',
    medium: 'text-yellow-700',
    low: 'text-green-700',
  };

  return (
    <motion.div
      className={`insight-card p-6 rounded-lg shadow-lg border-l-4 ${severityClasses[severity]} flex flex-col h-full`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex items-start mb-3">
        <div className={`mr-3 p-2 rounded-full ${severityTextClasses[severity]} ${severityClasses[severity]}`}>{icon}</div>
        <h4 className={`text-xl font-semibold ${severityTextClasses[severity]}`}>{title}</h4>
      </div>
      <p className="text-gray-700 text-sm mb-3 flex-grow">{description}</p>
      {savings && (
        <p className="text-green-600 font-bold text-md mt-auto">
          Potential Savings: {savings}
        </p>
      )}
      {impact && (
        <p className={`${severityTextClasses[severity]} font-semibold text-sm mt-auto`}>
          Impact: {impact}
        </p>
      )}
    </motion.div>
  );
};

export default InsightCard; 