#!/usr/bin/env node

import fs from 'fs/promises';
import path from 'path';

console.log('📦 Consolidating Restaurant AI Consulting codebase...');

// Define the files to include in the consolidation
const filesToInclude = [
  'restaurant-ai-consulting/package.json',
  'restaurant-ai-consulting/postcss.config.mjs',
  'restaurant-ai-consulting/eslint.config.mjs',
  'restaurant-ai-consulting/next.config.ts',
  'restaurant-ai-consulting/tsconfig.json',
  'restaurant-ai-consulting/src/app/layout.tsx',
  'restaurant-ai-consulting/src/app/page.tsx',
  'restaurant-ai-consulting/src/app/case-studies/[slug]/page.tsx',
  'restaurant-ai-consulting/src/components/ProgressSteps.tsx',
  'restaurant-ai-consulting/src/lib/utils.ts',
  'restaurant-ai-consulting/components.json',
  'restaurant-ai-consulting/README.md',
  // Backend files
  'restaurant-ai-consulting/backend/main.py',
  'restaurant-ai-consulting/backend/requirements.txt',
  'restaurant-ai-consulting/backend/README.md',
  'restaurant-ai-consulting/backend/documentation.md',
  'restaurant-ai-consulting/backend/restaurant_consultant/restaurant_data_aggregator_module.py',
  'restaurant-ai-consulting/backend/restaurant_consultant/llm_analyzer_module.py',
  'restaurant-ai-consulting/backend/restaurant_consultant/outreach_automation_module.py'
];

// Create output content
let consolidatedContent = `# Restaurant AI Consulting - Complete Codebase
Generated on: ${new Date().toISOString()}

This file contains all the relevant source code for the Restaurant AI Consulting landing page application.

## Project Overview
- **Framework**: Next.js 15 with TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **Features**: Interactive landing page, case studies, AI demo tools
- **Architecture**: App Router, Server/Client components, Responsive design
- **Backend**: FastAPI with modular Python scripts for data aggregation, LLM analysis, and outreach automation.

## File Structure
`;

// Add file tree structure
consolidatedContent += `
\`\`\`
restaurant-ai-consulting/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── README.md
│   ├── documentation.md
│   └── restaurant_consultant/
│       ├── llm_analyzer_module.py
│       ├── outreach_automation_module.py
│       └── restaurant_data_aggregator_module.py
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx (main landing page)
│   │   └── case-studies/
│   │       └── [slug]/
│   │           └── page.tsx (dynamic case study pages)
│   │   
│   ├── components/
│   │   └── ui/ (shadcn/ui components)
│   └── lib/
│       └── utils.ts
├── public/
├── package.json
├── tailwind.config.ts
├── next.config.ts
└── tsconfig.json
\`\`\`

---

`;

// Process each file
filesToInclude.forEach(async filePath => {
  const fullPath = path.join(process.cwd(), filePath);
  
  try {
    const content = await fs.readFile(fullPath, 'utf8');
    const fileExtension = path.extname(filePath).slice(1) || 'text';
    
    consolidatedContent += `## ${filePath}\n\n`;
    consolidatedContent += `\`\`\`${fileExtension}\n${content}\n\`\`\`\n\n---\n\n`;
    
    console.log(`✅ Added: ${filePath}`);
  } catch (error) {
    console.error(`❌ Error reading ${filePath}:`, error.message);
    consolidatedContent += `## ${filePath}\n\n*Error reading file: ${error.message}*\n\n---\n\n`;
  }
});

// Add project stats
const stats = {
  totalFiles: filesToInclude.length,
  consolidatedSize: Math.round(consolidatedContent.length / 1024),
  generatedAt: new Date().toLocaleString()
};

consolidatedContent += `## Project Statistics

- **Total Files Included**: ${stats.totalFiles}
- **Consolidated File Size**: ~${stats.consolidatedSize}KB
- **Generated**: ${stats.generatedAt}

## Key Features Implemented

### 🎯 Landing Page Components
- Hero section with value proposition
- Interactive product showcase with 3 demo tabs
- Service packages with pricing
- Real case studies with detailed narratives
- Interactive AI demo tools (4 different analyzers)
- Social proof and testimonials
- Mobile-responsive design

### 📊 Case Study System
- Dynamic routing for individual case studies
- Detailed problem/solution/results format
- Rich content with metrics and quotes
- Consistent branding and navigation

### 🔧 Technical Implementation
- TypeScript for type safety
- Tailwind CSS for styling
- shadcn/ui for consistent UI components
- Framer Motion for animations
- Recharts for data visualization
- Proper SEO structure
- Component-based architecture

### 🎨 UI/UX Features
- Modern gradient designs
- Interactive elements with hover effects
- Loading states for demo tools
- Responsive grid layouts
- Consistent color scheme and typography
- Accessibility considerations

## Dependencies Overview
- **Next.js 15**: Latest React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first CSS framework
- **shadcn/ui**: High-quality UI component library
- **Framer Motion**: Animation library
- **Recharts**: Charting library for data visualization
- **Lucide React**: Icon library

## Architecture Notes
- **App Router**: Modern Next.js routing with file-based structure
- **Server/Client Components**: Optimized rendering strategy
- **Dynamic Routes**: Case studies use [slug] dynamic routing
- **Component Composition**: Reusable UI components
- **State Management**: React hooks for local state
- **Responsive Design**: Mobile-first approach

---

*This consolidated file was generated automatically for code review purposes.*
`;

// Write the consolidated file
const outputPath = path.join(process.cwd(), 'consolidated-codebase.md');

try {
  await fs.writeFile(outputPath, consolidatedContent);
  console.log(`\n🎉 Successfully created consolidated codebase!`);
  console.log(`📁 Output: ${outputPath}`);
  console.log(`📊 Size: ~${stats.consolidatedSize}KB`);
  console.log(`\n💡 You can now send this file to your CTO for review.`);
} catch (error) {
  console.error('❌ Error writing consolidated file:', error.message);
  process.exit(1);
} 