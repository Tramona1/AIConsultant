import React from 'react';
import { motion } from 'framer-motion';

interface ProgressStepsProps {
  currentStep: number;
  steps: string[];
}

const ProgressSteps: React.FC<ProgressStepsProps> = ({ currentStep, steps }) => {
  console.log('Rendering ProgressSteps with currentStep:', currentStep);
  return (
    <div className="flex items-center justify-between w-full mb-4">
      {steps.map((step, index) => (
        <React.Fragment key={index}>
          <motion.div
            className={`flex flex-col items-center text-center ${index <= currentStep ? 'text-blue-600' : 'text-gray-400'}`}
            initial={{ opacity: 0.5 }}
            animate={{ opacity: index <= currentStep ? 1 : 0.5 }}
          >
            <motion.div
              className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${index <= currentStep ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-400 bg-white'}`}
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
            >
              {index + 1}
            </motion.div>
            <p className="text-xs mt-1 w-24">{step}</p>
          </motion.div>
          {index < steps.length - 1 && (
            <motion.div
              className="flex-1 h-1 mx-2 rounded"
              initial={{ width: 0, backgroundColor: '#E5E7EB' /* gray-200 */ }}
              animate={{
                width: '100%',
                backgroundColor: index < currentStep ? '#3B82F6' /* blue-500 */ : '#E5E7EB' /* gray-200 */,
              }}
              transition={{ duration: 0.5, delay: index * 0.2 }}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

export default ProgressSteps; 