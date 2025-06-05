import React from 'react';
import { motion } from 'framer-motion';

interface TestimonialCardProps {
  quote: string;
  author: string;
  role: string;
  metric: string;
}

const TestimonialCard: React.FC<TestimonialCardProps> = ({ quote, author, role, metric }) => {
  console.log('Rendering TestimonialCard for author:', author);
  return (
    <motion.div
      className="testimonial-card bg-white p-8 rounded-xl shadow-xl flex flex-col h-full border-t-4 border-blue-500"
      initial={{ opacity: 0, scale: 0.95 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.5 }}
    >
      <p className="text-gray-700 italic text-lg mb-6 flex-grow">&quot;{quote}&quot;</p>
      <div className="mt-auto">
        <p className="font-bold text-gray-900 text-md">- {author}</p>
        <p className="text-sm text-gray-500 mb-3">{role}</p>
        <p className="text-md text-blue-600 font-semibold bg-blue-50 p-2 rounded inline-block">
          Key Result: {metric}
        </p>
      </div>
    </motion.div>
  );
};

export default TestimonialCard; 