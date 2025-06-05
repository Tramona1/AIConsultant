#!/usr/bin/env node

// =============================================================================
// RESTAURANT AI CONSULTING - CONSOLIDATED ENHANCED SCRAPER
// =============================================================================
// Version: 2.0 - Dynamic Discovery & Screenshot Capture
// Last Updated: 2025-06-01
// Features: Dynamic URL discovery, comprehensive business intelligence, screenshots
// =============================================================================

import 'dotenv/config';
import { Stagehand } from '@browserbasehq/stagehand';
import { z } from 'zod';
import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';

console.error('🚀 CONSOLIDATED Enhanced Restaurant Scraper starting...');

class ConsolidatedRestaurantScraper {
  constructor() {
    try {
      this.stagehand = new Stagehand({
        env: 'LOCAL',
        modelName: "gpt-4o-mini",
        modelClientOptions: {
          apiKey: process.env.OPENAI_API_KEY,
        },
        verbose: 1,
        headless: false,
        browserOptions: {
          args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-features=VizDisplayCompositor',
            '--disable-web-security',
            '--disable-features=TranslateUI',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-images',
            '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
          ]
        }
      });
      
      this.log('✅ CONSOLIDATED Enhanced Restaurant Scraper initialized');
    } catch (initError) {
      this.log(`❌ Failed to initialize Stagehand: ${initError.message}`);
      this.stagehand = null;
    }
    
    this.logFile = path.join(process.cwd(), 'consolidated-scraper.log');
  }

  log(message) {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] ${message}`;
    
    console.error(logMessage);
    
    try {
      fs.appendFileSync(this.logFile, logMessage + '\n');
    } catch (err) {
      console.error('Failed to write to log file:', err.message);
    }
  }

  async scrapeRestaurant(url) {
    this.log(`🕷️ Starting CONSOLIDATED comprehensive website crawling for: ${url}`);
    
    const results = {
      url: url,
      scrapedAt: new Date().toISOString(),
      pages: {},
      combinedData: null,
      crawlingStrategy: 'consolidated_comprehensive',
      version: '2.0'
    };

    try {
      await this.stagehand.init();
      this.log(`✅ Stagehand initialized successfully`);
      
      await this.addStealth();
      this.log(`🥷 Stealth mode activated`);

      await this.stagehand.page.goto(url, { timeout: 30000 });
      await this.waitRandomDelay(2000, 4000);
      this.log(`✅ Navigated to homepage`);

      this.log(`🔍 Starting CONSOLIDATED comprehensive page discovery...`);
      const discoveredPages = await this.discoverAllRelevantPages(url);
      this.log(`📋 Discovered ${discoveredPages.length} relevant pages to crawl`);

      const homepageData = await this.extractPageData(url, 'homepage');
      results.pages.homepage = homepageData;

      for (const pageInfo of discoveredPages) {
        try {
          this.log(`🔗 CONSOLIDATED crawling: ${pageInfo.type} - ${pageInfo.url}`);
          await this.stagehand.page.goto(pageInfo.url, { timeout: 20000 });
          await this.waitRandomDelay(2000, 4000);
          
          const pageData = await this.extractPageData(pageInfo.url, pageInfo.type);
          results.pages[pageInfo.type] = pageData;
          
          this.log(`✅ Successfully crawled ${pageInfo.type}: ${pageData.menuItems?.length || 0} menu items found`);
          
        } catch (error) {
          this.log(`❌ Failed to crawl ${pageInfo.url}: ${error.message.substring(0, 50)}...`);
          results.pages[pageInfo.type] = { error: error.message, url: pageInfo.url };
        }
      }

      results.combinedData = await this.combineAllPageData(results.pages, url);
      this.log(`🔄 CONSOLIDATED data combined from ${Object.keys(results.pages).length} pages`);
      
      this.log(`🎉 CONSOLIDATED comprehensive crawling complete! ${Object.keys(results.pages).length} pages analyzed`);
      this.log(`📊 TOTAL CONSOLIDATED RESULTS: ${results.combinedData.menuItems?.length || 0} menu items`);
      
      return results;

    } catch (error) {
      this.log(`💥 CONSOLIDATED scraping error: ${error.message}`);
      results.error = error.message;
      return results;
    } finally {
      if (this.stagehand) {
        await this.stagehand.close();
        this.log(`🔒 CONSOLIDATED session closed`);
      }
    }
  }

  async discoverAllRelevantPages(baseUrl) {
    this.log('🔍 CONSOLIDATED DYNAMIC DISCOVERY - finding ALL navigation...');
    
    const discoveredPages = [];
    const baseUrlObj = new URL(baseUrl);
    
    try {
      // CONSOLIDATED Strategy 1: DYNAMIC HEADER NAVIGATION EXTRACTION
      this.log('📍 CONSOLIDATED Strategy 1: Dynamic header navigation extraction...');
      const headerNavigation = await this.stagehand.page.extract({
        instruction: `Extract ALL actual clickable navigation links from this website.

        CRITICAL: Find all <a> tags and clickable elements that have href attributes.
        Look in these areas:
        - Header navigation menu
        - Main navigation bar
        - Top navigation links
        - Navigation dropdowns
        - Menu buttons
        
        For each link found, extract:
        1. The ACTUAL href URL (like "/menu", "/about", "/products", "https://example.com/page")
        2. The visible text of the link
        3. A guess at what type of content it leads to
        
        IMPORTANT: Only include links that go to pages on THIS website.
        Do NOT include external links (social media, etc.) unless they're important.
        
        Example good URLs: "/menu", "/about-us", "/shop", "/sauces-rubs", "/pits"
        Example bad URLs: "javascript:void(0)", "#", "mailto:", "tel:"`,
        schema: z.object({
          headerNavigation: z.array(z.object({
            url: z.string().describe("The actual href attribute value"),
            text: z.string().describe("The visible text of the link"),
            contentType: z.string().describe("What type of content this likely contains"),
            prominence: z.number().describe("How prominent this link appears (1-10)")
          }))
        })
      });

      if (headerNavigation.headerNavigation) {
        this.log(`🔍 CONSOLIDATED processing ${headerNavigation.headerNavigation.length} header navigation items...`);
        for (const navItem of headerNavigation.headerNavigation) {
          this.log(`   📋 Raw navigation item: "${navItem.text}" -> "${navItem.url}"`);
          
          const fullUrl = this.resolveUrl(navItem.url, baseUrl);
          this.log(`   🔗 Resolved URL: ${fullUrl}`);
          
          if (fullUrl && this.isValidRestaurantUrl(fullUrl, baseUrlObj.hostname)) {
            discoveredPages.push({
              url: fullUrl,
              type: this.determineContentType(navItem.text, fullUrl, navItem.contentType),
              source: 'consolidated_header_navigation',
              confidence: navItem.prominence || 7,
              linkText: navItem.text,
              expectedContent: navItem.contentType
            });
            this.log(`   ✅ CONSOLIDATED added: ${navItem.text} -> ${fullUrl}`);
          } else {
            this.log(`   ❌ CONSOLIDATED filtered: ${navItem.text} -> ${navItem.url} (invalid URL)`);
          }
        }
      } else {
        this.log(`⚠️ CONSOLIDATED: No header navigation found`);
      }

      const uniquePages = this.deduplicatePages(discoveredPages);
      
      const sortedPages = uniquePages
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 12);

      this.log(`✅ CONSOLIDATED DISCOVERY complete: ${sortedPages.length} unique pages found`);
      
      sortedPages.forEach(page => {
        this.log(`   📋 CONSOLIDATED ${page.type.toUpperCase()}: ${page.linkText} (confidence: ${page.confidence})`);
      });
      
      return sortedPages;

    } catch (error) {
      this.log(`❌ CONSOLIDATED page discovery failed: ${error.message}`);
      return [];
    }
  }

  determineContentType(linkText, url, suggestedType) {
    const text = linkText.toLowerCase();
    const urlLower = url.toLowerCase();
    
    // CONSOLIDATED Enhanced content type detection
    if (text.includes('menu') || urlLower.includes('menu')) return 'menu';
    if (text.includes('food') || text.includes('eat') || text.includes('dining')) return 'menu';
    if (text.includes('drink') || text.includes('beverage') || text.includes('bar')) return 'menu';
    if (text.includes('shop') || text.includes('store') || text.includes('market')) return 'products';
    if (text.includes('merch') || text.includes('merchandise') || text.includes('gear')) return 'products';
    if (text.includes('sauce') || text.includes('spice') || text.includes('rub')) return 'products';
    if (text.includes('pit') || text.includes('smoker') || text.includes('grill')) return 'products';
    if (text.includes('catering') || text.includes('cater')) return 'services';
    if (text.includes('event') || text.includes('party') || text.includes('celebration')) return 'services';
    if (text.includes('delivery') || text.includes('takeout') || text.includes('pickup')) return 'services';
    if (text.includes('shipping') || text.includes('mail') || text.includes('send')) return 'services';
    if (text.includes('about') || text.includes('story') || text.includes('our')) return 'about';
    if (text.includes('contact') || text.includes('reach') || text.includes('call')) return 'contact';
    if (text.includes('location') || text.includes('address') || text.includes('find')) return 'operations';
    if (text.includes('hours') || text.includes('open') || text.includes('close')) return 'operations';
    if (text.includes('order') || text.includes('online') || text.includes('advance')) return 'ordering';
    if (text.includes('gallery') || text.includes('photo') || text.includes('image')) return 'media';

    if (suggestedType) return suggestedType;
    return 'other';
  }

  deduplicatePages(pages) {
    const seen = new Set();
    return pages.filter(page => {
      const key = page.url.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  async extractPageData(url, pageType) {
    this.log(`📊 CONSOLIDATED extracting data from ${pageType}...`);
    
    const extractedData = {
      url: url,
      pageType: pageType,
      scrapedAt: new Date().toISOString(),
      contentAnalysis: {
        extractionStrategy: `consolidated_${pageType}`,
        dataTypes: [],
        businessIntelligence: {}
      },
      screenshots: []
    };

    try {
      // CONSOLIDATED: Take screenshot for visual proof
      this.log(`📸 CONSOLIDATED taking screenshot of ${pageType}...`);
      const timestamp = Date.now();
      const screenshotPath = `consolidated_screenshots/${pageType}_${timestamp}.png`;
      
      try {
        const screenshotsDir = path.join(process.cwd(), 'consolidated_screenshots');
        if (!fs.existsSync(screenshotsDir)) {
          fs.mkdirSync(screenshotsDir, { recursive: true });
        }
        
        await this.stagehand.page.screenshot({ 
          path: screenshotPath,
          fullPage: true
        });
        
        extractedData.screenshots.push({
          path: screenshotPath,
          timestamp: timestamp,
          pageType: pageType,
          url: url
        });
        
        this.log(`✅ CONSOLIDATED screenshot saved: ${screenshotPath}`);
      } catch (screenshotError) {
        this.log(`⚠️ CONSOLIDATED screenshot failed: ${screenshotError.message}`);
      }

      // CONSOLIDATED: Extract comprehensive business data
      const comprehensiveData = await this.stagehand.page.extract({
        instruction: `CONSOLIDATED COMPREHENSIVE BUSINESS ANALYSIS - Extract ALL business information:
        
        CONTENT ANALYSIS:
        - All text content that provides business intelligence
        - Contact information and business details
        - Services, products, or offerings mentioned
        - Menu items with prices if available
        - Company information and positioning
        - Any unique features or differentiators
        
        Extract everything that provides business value and intelligence.`,
        schema: z.object({
          name: z.string().nullable(),
          phone: z.string().nullable(),
          email: z.string().nullable(),
          address: z.string().nullable(),
          businessContent: z.array(z.string()).nullable(),
          offerings: z.array(z.string()).nullable(),
          menuItems: z.array(z.object({
            name: z.string(),
            price: z.string().nullable(),
            description: z.string().nullable(),
            category: z.string().nullable()
          })).nullable(),
          products: z.array(z.object({
            name: z.string(),
            price: z.string().nullable(),
            description: z.string().nullable(),
            category: z.string().nullable()
          })).nullable(),
          services: z.array(z.object({
            name: z.string(),
            description: z.string().nullable(),
            pricing: z.string().nullable()
          })).nullable(),
          pricing: z.array(z.string()).nullable(),
          features: z.array(z.string()).nullable(),
          contactInfo: z.object({
            phone: z.string().nullable(),
            email: z.string().nullable(),
            address: z.string().nullable(),
            hours: z.string().nullable()
          }).nullable()
        })
      });

      Object.assign(extractedData, comprehensiveData);
      extractedData.contentAnalysis.dataTypes = Object.keys(comprehensiveData);
      
      this.log(`✅ CONSOLIDATED extraction complete for ${pageType}: ${extractedData.contentAnalysis.dataTypes.length} data types`);

    } catch (error) {
      this.log(`⚠️ CONSOLIDATED extraction failed: ${error.message}`);
      
      try {
        const basicData = await this.stagehand.page.extract({
          instruction: `CONSOLIDATED basic extraction: company name, contact info, and important content`,
          schema: z.object({
            name: z.string().nullable(),
            phone: z.string().nullable(),
            address: z.string().nullable(),
            email: z.string().nullable(),
            businessContent: z.array(z.string()).nullable()
          })
        });
        Object.assign(extractedData, basicData);
        this.log(`✅ CONSOLIDATED basic extraction successful for ${pageType}`);
      } catch (fallbackError) {
        this.log(`❌ CONSOLIDATED all extraction failed for ${pageType}`);
      }
    }

    return extractedData;
  }

  async combineAllPageData(pages, originalUrl) {
    this.log('🔄 CONSOLIDATED combining business intelligence...');
    
    const combined = {
      name: null,
      email: null,
      phone: null,
      address: null,
      
      businessIntelligence: {
        menuItems: [],
        products: [],
        services: [],
        companyInfo: {},
        revenueStreams: [],
        competitiveAdvantages: [],
        businessModel: []
      },
      
      menuItems: [],
      socialLinks: [],
      openingHours: null,
      restaurantType: null,
      
      url: originalUrl,
      scrapedAt: new Date().toISOString(),
      pagesAnalyzed: [],
      crawlingStats: {
        totalPagesFound: Object.keys(pages).length,
        successfulExtractions: 0,
        contentTypes: {},
        totalMenuItems: 0,
        totalProducts: 0,
        totalServices: 0
      },
      consolidatedVersion: '2.0'
    };

    for (const [pageType, pageData] of Object.entries(pages)) {
      if (!pageData || pageData.error) continue;
      
      combined.pagesAnalyzed.push(pageType);
      combined.crawlingStats.successfulExtractions++;

      combined.name = combined.name || pageData.name;
      combined.email = combined.email || pageData.email;
      combined.phone = combined.phone || pageData.phone;
      combined.address = combined.address || pageData.address;

      if (pageData.menuItems && pageData.menuItems.length > 0) {
        combined.businessIntelligence.menuItems = combined.businessIntelligence.menuItems.concat(pageData.menuItems);
        combined.menuItems = combined.menuItems.concat(pageData.menuItems);
        combined.crawlingStats.totalMenuItems += pageData.menuItems.length;
        this.log(`📋 CONSOLIDATED added ${pageData.menuItems.length} menu items from ${pageType}`);
      }

      if (pageData.products && pageData.products.length > 0) {
        combined.businessIntelligence.products = combined.businessIntelligence.products.concat(pageData.products);
        combined.crawlingStats.totalProducts += pageData.products.length;
        this.log(`🛍️ CONSOLIDATED added ${pageData.products.length} products from ${pageType}`);
      }

      if (pageData.services && pageData.services.length > 0) {
        combined.businessIntelligence.services = combined.businessIntelligence.services.concat(pageData.services);
        combined.crawlingStats.totalServices += pageData.services.length;
        this.log(`🔧 CONSOLIDATED added ${pageData.services.length} services from ${pageType}`);
      }

      if (pageData.businessContent && pageData.businessContent.length > 0) {
        this.log(`📄 CONSOLIDATED added business content from ${pageType}`);
      }
    }

    combined.businessIntelligence.menuItems = this.deduplicateMenuItems(combined.businessIntelligence.menuItems);
    combined.menuItems = this.deduplicateMenuItems(combined.menuItems);
    
    this.log(`✅ CONSOLIDATED intelligence combined from ${combined.pagesAnalyzed.length} pages:`);
    this.log(`   📋 Menu items: ${combined.crawlingStats.totalMenuItems}`);
    this.log(`   🛍️ Products: ${combined.crawlingStats.totalProducts}`);
    this.log(`   🔧 Services: ${combined.crawlingStats.totalServices}`);
    
    return combined;
  }

  deduplicateMenuItems(menuItems) {
    const seen = new Set();
    return menuItems.filter(item => {
      const key = `${item.name}_${item.price}_${item.category}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  resolveUrl(url, baseUrl) {
    try {
      if (url.startsWith('http')) return url;
      if (url.startsWith('/')) {
        const baseUrlObj = new URL(baseUrl);
        return `${baseUrlObj.protocol}//${baseUrlObj.host}${url}`;
      }
      return new URL(url, baseUrl).href;
    } catch {
      return null;
    }
  }

  isValidRestaurantUrl(url, hostname) {
    try {
      if (!url || typeof url !== 'string') return false;
      
      if (url.startsWith('javascript:') || 
          url.startsWith('mailto:') || 
          url.startsWith('tel:') || 
          url === '#' || 
          url.startsWith('#')) {
        return false;
      }
      
      if (/^\d+$/.test(url)) {
        this.log(`⚠️ CONSOLIDATED filtering numeric non-URL: ${url}`);
        return false;
      }
      
      if (!url.includes('/') && !url.startsWith('http')) {
        this.log(`⚠️ CONSOLIDATED filtering invalid format: ${url}`);
        return false;
      }
      
      const urlObj = new URL(url, `https://${hostname}`);
      const isValidDomain = urlObj.hostname === hostname || urlObj.hostname.endsWith(`.${hostname}`);
      
      if (!isValidDomain) {
        this.log(`⚠️ CONSOLIDATED filtering external URL: ${url}`);
        return false;
      }
      
      return true;
    } catch (error) {
      this.log(`⚠️ CONSOLIDATED URL validation error: ${error.message}`);
      return false;
    }
  }

  async addStealth() {
    this.log('🥷 CONSOLIDATED adding stealth measures...');
    
    try {
      await this.stagehand.page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
      await this.stagehand.page.setViewport({ width: 1366, height: 768 });
      this.log('✅ CONSOLIDATED stealth measures applied');
    } catch (error) {
      this.log(`⚠️ CONSOLIDATED stealth failed: ${error.message}`);
    }
  }

  async waitRandomDelay(min = 1000, max = 3000) {
    const delay = Math.random() * (max - min) + min;
    await this.stagehand.page.waitForTimeout(delay);
  }

  async main() {
    const args = process.argv.slice(2);
    
    if (args.length === 0 || args.includes('--help')) {
      console.log(`
🕷️ CONSOLIDATED Enhanced Restaurant Website Scraper

Usage: node consolidated-codebase.js <url>

Examples:
  node consolidated-codebase.js https://franklinbarbecue.com

CONSOLIDATED Features:
  📋 Dynamic page discovery
  🍽️ Comprehensive menu extraction  
  🛍️ Product analysis
  🔧 Service offerings
  🏢 Company intelligence
  📸 Screenshot capture
  📊 Complete business intelligence
      `);
      return;
    }

    const url = args[0];

    if (!url || !url.startsWith('http')) {
      console.error('❌ Please provide a valid URL starting with http:// or https://');
      return;
    }

    try {
      const results = await this.scrapeRestaurant(url);
      
      console.log('\n' + '='.repeat(80));
      console.log('📊 CONSOLIDATED COMPREHENSIVE BUSINESS INTELLIGENCE');
      console.log('='.repeat(80));
      
      if (results.combinedData) {
        const data = results.combinedData;
        const bi = data.businessIntelligence;
        
        console.log(`🏠 Restaurant: ${data.name || 'Name not found'}`);
        console.log(`📍 Address: ${data.address || 'Address not found'}`);
        console.log(`📞 Phone: ${data.phone || 'Phone not found'}`);
        console.log(`📧 Email: ${data.email || 'Email not found'}`);
        
        console.log(`\n📊 CONSOLIDATED BUSINESS ANALYSIS:`);
        console.log(`   🍽️ Menu Items: ${data.crawlingStats?.totalMenuItems || 0}`);
        console.log(`   🛍️ Products: ${data.crawlingStats?.totalProducts || 0}`);
        console.log(`   🔧 Services: ${data.crawlingStats?.totalServices || 0}`);
        console.log(`   📋 Pages Crawled: ${data.pagesAnalyzed?.length || 0}`);
        console.log(`   📸 Version: ${data.consolidatedVersion || '2.0'}`);
        
        if (bi?.menuItems && bi.menuItems.length > 0) {
          console.log(`\n📋 CONSOLIDATED SAMPLE MENU ITEMS:`);
          bi.menuItems.slice(0, 5).forEach(item => {
            console.log(`   • ${item.name}${item.price ? ` - ${item.price}` : ''}${item.category ? ` (${item.category})` : ''}`);
          });
          if (bi.menuItems.length > 5) {
            console.log(`   ... and ${bi.menuItems.length - 5} more items`);
          }
        }
        
        if (bi?.products && bi.products.length > 0) {
          console.log(`\n🛍️ CONSOLIDATED SAMPLE PRODUCTS:`);
          bi.products.slice(0, 3).forEach(product => {
            console.log(`   • ${product.name}${product.price ? ` - ${product.price}` : ''}`);
          });
        }
        
        if (bi?.services && bi.services.length > 0) {
          console.log(`\n🔧 CONSOLIDATED SAMPLE SERVICES:`);
          bi.services.slice(0, 3).forEach(service => {
            console.log(`   • ${service.name}${service.pricing ? ` - ${service.pricing}` : ''}`);
          });
        }
      }
      
      console.log('='.repeat(80));
      
      // CONSOLIDATED: Save results
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `consolidated-results-${timestamp}.json`;
      
      fs.writeFileSync(filename, JSON.stringify(results, null, 2));
      console.log(`💾 CONSOLIDATED results saved to: ${filename}`);
      
      // CONSOLIDATED: Report what was saved
      console.log(`\n📁 CONSOLIDATED DATA SAVED:`);
      console.log(`   📄 Complete results: ${filename} (${Math.round(fs.statSync(filename).size / 1024)}KB)`);
      console.log(`   📋 Detailed logs: consolidated-scraper.log`);
      
      let totalScreenshots = 0;
      if (results.pages) {
        Object.values(results.pages).forEach(page => {
          if (page.screenshots && page.screenshots.length > 0) {
            totalScreenshots += page.screenshots.length;
            page.screenshots.forEach(screenshot => {
              try {
                const size = Math.round(fs.statSync(screenshot.path).size / (1024 * 1024) * 10) / 10;
                console.log(`   📸 Screenshot: ${screenshot.path} (${size}MB)`);
              } catch {
                console.log(`   📸 Screenshot: ${screenshot.path}`);
              }
            });
          }
        });
      }
      
      console.log(`\n💡 CONSOLIDATED: All data and ${totalScreenshots} screenshots saved!`);
      
    } catch (error) {
      console.error(`💥 CONSOLIDATED scraping failed: ${error.message}`);
      process.exit(1);
    }
  }
}

// =============================================================================
// CONSOLIDATED EXECUTION
// =============================================================================

if (process.argv[1] && process.argv[1].endsWith('consolidated-codebase.js')) {
  console.error('✅ CONSOLIDATED Enhanced CLI execution detected!');
  
  const scraper = new ConsolidatedRestaurantScraper();
  
  scraper.main().catch(error => {
    console.error('💥 CONSOLIDATED execution failed:', error.message);
    process.exit(1);
  });
} else {
  console.error('ℹ️ CONSOLIDATED module imported, not executing CLI');
}

export default ConsolidatedRestaurantScraper; 