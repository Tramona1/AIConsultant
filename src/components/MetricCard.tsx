import React from 'react';
import { motion } from 'framer-motion';

interface MetricCardProps {
  number: string;
  label: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ number, label }) => {
  console.log('Rendering MetricCard with label:', label);
  return (
    <motion.div
      className="metric-card p-6 bg-white rounded-lg shadow-lg text-center"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.5 }}
      transition={{ duration: 0.4 }}
    >
      <div className="text-5xl font-bold text-blue-600 mb-2">{number}</div>
      <div className="text-gray-700 text-lg">{label}</div>
    </motion.div>
  );
};

export default MetricCard; 