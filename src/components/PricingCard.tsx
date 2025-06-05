import React from 'react';
import { motion } from 'framer-motion';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface PricingCardProps {
  name: string;
  price: string;
  description: string;
  features: string[];
  popular?: boolean;
}

const PricingCard: React.FC<PricingCardProps> = ({ name, price, description, features, popular }) => {
  console.log('Rendering PricingCard for plan:', name);
  return (
    <motion.div
      className={`pricing-card border rounded-xl p-8 shadow-lg flex flex-col h-full relative ${popular ? 'border-blue-600 border-2' : 'border-gray-200'}`}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.5, delay: popular ? 0.1 : 0 }}
    >
      {popular && (
        <Badge className="absolute top-0 -translate-y-1/2 left-1/2 -translate-x-1/2 bg-blue-600 text-white px-4 py-1 text-sm font-semibold rounded-full shadow-md">
          Most Popular
        </Badge>
      )}
      <h3 className="text-3xl font-semibold mb-3 text-gray-800">{name}</h3>
      <p className={`text-5xl font-bold mb-2 ${popular ? 'text-blue-600' : 'text-gray-900'}`}>{price}
        {name !== 'Enterprise' && <span className="text-lg font-normal text-gray-500">/mo</span>}
      </p>
      <p className="text-gray-600 mb-8 text-sm">{description}</p>
      <ul className="space-y-3 mb-10 text-gray-700 flex-grow">
        {features.map((feature, index) => (
          <li key={index} className="flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className={`h-5 w-5 mr-2 ${popular ? 'text-blue-500' : 'text-green-500'}`} viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            {feature}
          </li>
        ))}
      </ul>
      <Button 
        className={`w-full mt-auto py-3 text-lg font-semibold ${popular ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-gray-100 hover:bg-gray-200 text-blue-600'}`}
        variant={popular ? 'default' : 'outline'}
      >
        {name === 'Enterprise' ? 'Contact Sales' : 'Choose Plan'}
      </Button>
    </motion.div>
  );
};

export default PricingCard; 