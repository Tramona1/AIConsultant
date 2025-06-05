import React from 'react';
import { motion } from 'framer-motion';
import { Badge } from "@/components/ui/badge";

interface StepCardProps {
  number: string;
  title: string;
  description: string;
  duration: string;
  icon: React.ReactNode;
}

const StepCard: React.FC<StepCardProps> = ({ number, title, description, duration, icon }) => {
  console.log('Rendering StepCard with title:', title);
  return (
    <motion.div
      className="step-card bg-white p-6 rounded-xl shadow-lg text-center flex flex-col items-center h-full border-t-4 border-purple-500"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.5 }}
    >
      <div className="text-purple-600 mb-4 p-3 bg-purple-100 rounded-full">
        {icon}
      </div>
      <h3 className="text-2xl font-semibold mb-2 text-gray-800">{number}. {title}</h3>
      <p className="text-gray-600 text-sm mb-4 flex-grow">{description}</p>
      <Badge variant="outline" className="mt-auto border-purple-500 text-purple-700">Duration: {duration}</Badge>
    </motion.div>
  );
};

export default StepCard; 