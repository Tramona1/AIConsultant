import 'dotenv/config';
import { Stagehand } from '@browserbasehq/stagehand';
import { z } from 'zod';
import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';
import AWS from 'aws-sdk';

// Debug: Log script start
console.error('🚀 Enhanced Restaurant Scraper starting...');

// Configure AWS S3
const s3 = new AWS.S3({
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
  region: process.env.AWS_REGION || 'us-west-2'
});

const S3_BUCKET = process.env.S3_BUCKET_NAME || 'restaurant-ai-screenshots';

class EnhancedRestaurantScraper {
  constructor() {
    try {
      this.stagehand = new Stagehand({
        env: 'LOCAL',
        modelName: "gpt-4o",
        modelClientOptions: {
          apiKey: process.env.OPENAI_API_KEY,
        },
        verbose: 1,
        headless: true, // MODERN: Use headless for better performance and stealth
        browserOptions: {
          // Enhanced anti-detection measures
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
            '--disable-images', // Faster loading
            '--disable-blink-features=AutomationControlled', // Anti-detection
            '--disable-infobars'
          ]
        }
      });
      
      this.log('MODERN EnhancedRestaurantScraper initialized with enhanced stealth and context-based spoofing');
    } catch (initError) {
      this.log(`Failed to initialize Stagehand: ${initError.message}`);
      this.stagehand = null;
    }
    
    this.logFile = path.join(process.cwd(), 'enhanced-scraper.log');
    this.jsonEndpoints = []; // Store captured JSON endpoints
    this.screenshotsSaved = new Set(); // Track screenshots to prevent over-screenshotting
    this.log('Modern EnhancedRestaurantScraper initialization completed');
    
    // COMPETITIVE MODE: Faster processing for competitor analysis
    this.competitiveMode = process.argv.includes('--competitive');
    if (this.competitiveMode) {
      this.log("🚀 COMPETITIVE MODE: Optimized for speed in parallel processing");
    }
  }

  log(message) {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] ${message}`;
    
    // Write to stderr (not stdout) to avoid contaminating JSON output
    console.error(logMessage);
    
    // Also write to log file
    try {
      fs.appendFileSync(this.logFile, logMessage + '\n');
    } catch (err) {
      console.error('Failed to write to log file:', err.message);
    }
  }

  async uploadScreenshotToS3(localPath, pageType, timestamp) {
    this.log(`☁️ Uploading screenshot to S3: ${localPath}`);
    
    try {
      // Check if AWS credentials are configured
      if (!process.env.AWS_ACCESS_KEY_ID || !process.env.AWS_SECRET_ACCESS_KEY) {
        this.log(`⚠️ AWS credentials not configured, skipping S3 upload`);
        return localPath; // Return local path as fallback
      }
      
      // Read the file
      const fileContent = fs.readFileSync(localPath);
      const fileName = `${pageType}_${timestamp}_${Date.now()}.png`;
      const s3Key = `restaurant-screenshots/${fileName}`;
      
      // Upload to S3 with modern security practices
      const uploadParams = {
        Bucket: S3_BUCKET,
        Key: s3Key,
        Body: fileContent,
        ContentType: 'image/png'
        // MODERN: Removed legacy ACL for better security
        // Use bucket policies or presigned URLs for public access instead
      };
      
      const result = await s3.upload(uploadParams).promise();
      const s3Url = result.Location;
      
      this.log(`✅ Screenshot uploaded to S3 (secure): ${s3Url}`);
      
      // Clean up local file
      try {
        fs.unlinkSync(localPath);
        this.log(`🗑️ Cleaned up local screenshot: ${localPath}`);
      } catch (cleanupError) {
        this.log(`⚠️ Failed to clean up local file: ${cleanupError.message}`);
      }
      
      return s3Url;
      
    } catch (error) {
      this.log(`❌ S3 upload failed: ${error.message}`);
      this.log(`📁 Keeping local screenshot: ${localPath}`);
      return localPath; // Return local path as fallback
    }
  }

  async scrapeRestaurant(url) {
    this.log(`🕷️ Starting MODERN website crawling with enhanced discovery for: ${url}`);
    
    const results = {
      url: url,
      scrapedAt: new Date().toISOString(),
      pages: {},
      combinedData: null,
      crawlingStrategy: 'enhanced_manual_crawl'
    };

    try {
      await this.stagehand.init();
      this.log(`✅ Stagehand initialized successfully`);
      
      // Apply stealth measures
      await this.addStealth();
      this.log(`🥷 Stealth mode activated`);

      // MODERN: Add request interception to catch JSON endpoints (FIXED: remove await)
      this.jsonEndpoints = [];
      
      this.stagehand.page.on('response', async (response) => {
        try {
          const contentType = response.headers()['content-type'] || '';
          const url = response.url();
          
          // Look for JSON responses that might contain menu data
          if (contentType.includes('application/json') && response.ok()) {
            this.log(`🔍 JSON endpoint detected: ${url}`);
            
            // Only capture relevant JSON endpoints (menu, product, food related)
            if (this.isMenuRelatedEndpoint(url)) {
              try {
                const jsonData = await response.json();
                
                // Deduplicate by URL to avoid re-processing
                const existingEndpoint = this.jsonEndpoints.find(ep => ep.url === url);
                if (!existingEndpoint) {
                  this.jsonEndpoints.push({
                    url: url,
                    data: jsonData,
                    timestamp: Date.now()
                  });
                  this.log(`✅ Captured menu-related JSON data from: ${url}`);
                } else {
                  this.log(`🔄 Skipping duplicate JSON endpoint: ${url}`);
                }
              } catch (jsonError) {
                this.log(`⚠️ Failed to parse JSON from ${url}: ${jsonError.message}`);
              }
            }
          }
        } catch (responseError) {
          // Ignore response parsing errors (keeping variable for clarity)
          void responseError;
        }
      });

      // Start by going to the homepage
      await this.stagehand.page.goto(url, { timeout: 30000 });
      
      // MODERN: Wait for network idle instead of arbitrary delay
      await this.stagehand.page.waitForLoadState('networkidle');
      this.log(`✅ Navigated to homepage and network is idle`);

      // ENHANCED: Comprehensive page discovery
      this.log(`🔍 Starting comprehensive page discovery...`);
      const discoveredPages = await this.discoverAllRelevantPages(url);
      this.log(`📋 Discovered ${discoveredPages.length} relevant pages to crawl`);

      // Extract homepage data first
      const homepageData = await this.extractPageData(url, 'homepage');
      results.pages.homepage = homepageData;

      // ENHANCED: Crawl ALL discovered pages with modern techniques
      const pagesToAnalyze = discoveredPages; // REMOVED: competitive mode limitations
      
      this.log(`🔍 Enhanced crawling starting: ${pagesToAnalyze.length} pages with FULL CONCURRENT processing`);
      
      // CONCURRENCY OPTIMIZATION: Process pages in parallel with multiple browser contexts
      const maxConcurrentPages = 2; // REDUCED: Process 2 pages simultaneously for better stability
      const pageChunks = [];
      for (let i = 0; i < pagesToAnalyze.length; i += maxConcurrentPages) {
        pageChunks.push(pagesToAnalyze.slice(i, i + maxConcurrentPages));
      }
      
      for (const chunk of pageChunks) {
        this.log(`🚀 Processing ${chunk.length} pages concurrently...`);
        
        const crawlPromises = chunk.map(async (pageInfo) => {
          let context = null;
          let page = null;
          
          try {
            this.log(`🔗 Crawling: ${pageInfo.type} - ${pageInfo.url}`);
            
            // Create new browser context for this page (enables true parallelism)
            const browser = await this.stagehand.browser();
            context = await browser.newContext({
              userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
              viewport: { width: 1366, height: 768 }
            });
            page = await context.newPage();
            
            // IMPROVED: Better timeout and error handling
            await page.goto(pageInfo.url, { 
              timeout: 15000,  // Reduced timeout for faster failure detection
              waitUntil: 'domcontentloaded'  // Faster loading strategy
            });
            
            // IMPROVED: Wait for content but with timeout
            try {
              await page.waitForLoadState('networkidle', { timeout: 10000 });
            } catch {
              this.log(`⚠️ Network idle timeout for ${pageInfo.type}, proceeding with extraction`);
            }
            
            // Create a context object for extraction
            const extractionContext = { page, url: pageInfo.url };
            const pageData = await this.extractPageDataModern(extractionContext, pageInfo.type);
            results.pages[pageInfo.type] = pageData;
            
            this.log(`✅ Successfully crawled ${pageInfo.type}: ${pageData.menuItems?.length || 0} menu items found`);
            
          } catch (error) {
            this.log(`❌ Failed to crawl ${pageInfo.url}: ${error.message.substring(0, 50)}...`);
            results.pages[pageInfo.type] = { error: error.message, url: pageInfo.url };
          } finally {
            // Clean up browser context and page for each concurrent process
            try {
              if (page) await page.close();
              if (context) await context.close();
            } catch (cleanupError) {
              this.log(`⚠️ Context cleanup failed for ${pageInfo.type}: ${cleanupError.message}`);
            }
          }
        });

        await Promise.all(crawlPromises);
      }

      // Process captured JSON endpoints for additional menu data
      if (this.jsonEndpoints.length > 0) {
        this.log(`🔍 Processing ${this.jsonEndpoints.length} captured JSON endpoints for menu data...`);
        await this.processJsonEndpoints(results);
      }

      // ENHANCED: Combine all data from all pages for holistic view
      results.combinedData = await this.combineAllPageData(results.pages, url);
      results.jsonEndpointsFound = this.jsonEndpoints.length;
      
      // FIXED: Add root-level dataQuality field that Python expects
      results.dataQuality = {
        name_extracted: !!(results.combinedData && results.combinedData.name),
        address_extracted: !!(results.combinedData && results.combinedData.address),
        phone_extracted: !!(results.combinedData && results.combinedData.phone),
        email_extracted: !!(results.combinedData && results.combinedData.email),
        menu_items_found: !!(results.combinedData && results.combinedData.menuItems && results.combinedData.menuItems.length > 0),
        products_found: !!(results.combinedData && results.combinedData.businessIntelligence && results.combinedData.businessIntelligence.products && results.combinedData.businessIntelligence.products.length > 0),
        services_found: !!(results.combinedData && results.combinedData.businessIntelligence && results.combinedData.businessIntelligence.services && results.combinedData.businessIntelligence.services.length > 0),
        social_links_found: !!(results.combinedData && results.combinedData.socialLinks && results.combinedData.socialLinks.length > 0)
      };
      
      this.log(`🔄 Combined data from ${Object.keys(results.pages).length} pages: ${results.combinedData.menuItems?.length || 0} total menu items`);
      
      this.log(`🎉 Enhanced crawling complete! ${Object.keys(results.pages).length} pages analyzed`);
      this.log(`📊 TOTAL MENU ITEMS FOUND: ${results.combinedData.menuItems?.length || 0}`);
      this.log(`🔗 JSON ENDPOINTS CAPTURED: ${this.jsonEndpoints.length}`);
      
      return results;

    } catch (error) {
      this.log(`💥 Critical scraping error: ${error.message}`);
      results.error = error.message;
      return results;
    } finally {
      if (this.stagehand) {
        await this.stagehand.close();
        this.log(`🔒 Stagehand session closed`);
      }
    }
  }

  isMenuRelatedEndpoint(url) {
    const urlLower = url.toLowerCase();
    
    // Check for menu-related keywords in the URL
    const menuKeywords = [
      'menu', 'food', 'dish', 'item', 'product', 'catalog',
      'restaurant', 'dining', 'eat', 'meal', 'course',
      'appetizer', 'entree', 'dessert', 'drink', 'beverage',
      'wine', 'beer', 'cocktail', 'bar', 'alcohol',
      'lunch', 'dinner', 'breakfast', 'brunch',
      'api/menu', 'api/food', 'api/products', 'api/items',
      '/menu/', '/food/', '/products/', '/items/',
      'getmenu', 'menuitems', 'fooditems'
    ];
    
    return menuKeywords.some(keyword => urlLower.includes(keyword));
  }

  determinePageTypeFromUrl(url) {
    const pathname = new URL(url).pathname.toLowerCase();
    
    // Enhanced URL-based page type detection
    if (pathname.includes('menu') || pathname.includes('food') || pathname.includes('dining')) return 'menu';
    if (pathname.includes('drink') || pathname.includes('wine') || pathname.includes('cocktail') || pathname.includes('bar')) return 'menu';
    if (pathname.includes('lunch') || pathname.includes('dinner') || pathname.includes('breakfast') || pathname.includes('brunch')) return 'menu';
    if (pathname.includes('product') || pathname.includes('shop') || pathname.includes('store') || pathname.includes('merch')) return 'products';
    if (pathname.includes('sauce') || pathname.includes('spice') || pathname.includes('rub') || pathname.includes('pit')) return 'products';
    if (pathname.includes('about') || pathname.includes('story') || pathname.includes('history')) return 'about';
    if (pathname.includes('contact') || pathname.includes('location') || pathname.includes('hour')) return 'contact';
    if (pathname.includes('service') || pathname.includes('cater') || pathname.includes('event') || pathname.includes('delivery')) return 'services';
    if (pathname.includes('ship') || pathname.includes('order')) return 'ordering';
    if (pathname === '/' || pathname === '') return 'homepage';
    
    return 'other';
  }

  async extractPageDataModern(context, pageType) {
    this.log(`📊 MODERN extracting data from ${pageType} page: ${context.url}`);
    
    const extractedData = {
      url: context.url,
      pageType: pageType,
      scrapedAt: new Date().toISOString(),
      contentAnalysis: {
        extractionStrategy: `modern_${pageType}`,
        dataTypes: [],
        businessIntelligence: {}
      },
      screenshots: []
    };

    try {
      // ENHANCED: Take screenshot for visual proof (SMART: only first of each type)
      this.log(`📸 ENHANCED taking screenshot of ${pageType}...`);
      const timestamp = Date.now();
      const screenshotPath = `consolidated_screenshots/${pageType}_${timestamp}.png`;
      
      // PRODUCTION: Smart screenshotting - only save first of each page type
      const shouldSaveScreenshot = !this.screenshotsSaved.has(pageType);
      
      if (shouldSaveScreenshot) {
        try {
          const screenshotsDir = path.join(process.cwd(), 'consolidated_screenshots');
          if (!fs.existsSync(screenshotsDir)) {
            fs.mkdirSync(screenshotsDir, { recursive: true });
          }
          
          await context.page.screenshot({ 
            path: screenshotPath,
            fullPage: true
          });
          
          const s3Url = await this.uploadScreenshotToS3(screenshotPath, pageType, timestamp);
          
          extractedData.screenshots.push({
            path: screenshotPath,
            s3Url: s3Url,
            timestamp: timestamp,
            pageType: pageType,
            url: context.url
          });
          
          // Mark this page type as screenshotted
          this.screenshotsSaved.add(pageType);
          
          this.log(`✅ ENHANCED screenshot saved (first of ${pageType}): ${screenshotPath}`);
        } catch (screenshotError) {
          this.log(`⚠️ ENHANCED screenshot failed: ${screenshotError.message}`);
        }
      } else {
        this.log(`🔄 SMART: Skipping screenshot for ${pageType} (already have one) - S3 cost optimization`);
      }

      // MODERN: Enhanced extraction with page-specific intelligence
      const comprehensiveInstruction = this.getPageSpecificExtractionInstruction(pageType);
      
      // FIXED: Wait longer for dynamic content to load
      this.log(`⏳ Waiting for dynamic content to fully load...`);
      await context.page.waitForTimeout(3000); // Give dynamic content time
      await context.page.waitForLoadState('networkidle');
      
      // SIMPLIFIED: Use simpler schema for better extraction success
      const comprehensiveData = await context.page.extract({
        instruction: comprehensiveInstruction,
        schema: z.object({
          // SIMPLIFIED: Basic business information
          name: z.string().nullable(),
          phone: z.string().nullable(),
          email: z.string().nullable(),
          address: z.string().nullable(),
          
          // SIMPLIFIED: Core content (reduced complexity)
          menuItems: z.array(z.object({
            name: z.string(),
            price: z.string().nullable(),
            description: z.string().nullable()
          })).nullable(),
          
          products: z.array(z.object({
            name: z.string(),
            price: z.string().nullable(),
            description: z.string().nullable()
          })).nullable(),
          
          services: z.array(z.object({
            name: z.string(),
            description: z.string().nullable()
          })).nullable(),
          
          // SIMPLIFIED: Contact info
          hours: z.string().nullable(),
          socialMedia: z.array(z.string()).nullable(),
          
          // SIMPLIFIED: Business content
          businessDescription: z.string().nullable(),
          specialties: z.array(z.string()).nullable()
        })
      });

      // Merge comprehensive data into extracted data
      Object.assign(extractedData, comprehensiveData);
      extractedData.contentAnalysis.dataTypes = Object.keys(comprehensiveData).filter(key => comprehensiveData[key] !== null);
      
      // Add business intelligence summary
      extractedData.contentAnalysis.businessIntelligence = {
        menuItemsFound: comprehensiveData.menuItems?.length || 0,
        productsFound: comprehensiveData.products?.length || 0,
        servicesFound: comprehensiveData.services?.length || 0,
        hasContact: !!(comprehensiveData.phone || comprehensiveData.email),
        hasHours: !!comprehensiveData.hours,
        hasSocialMedia: comprehensiveData.socialMedia?.length || 0,
        hasBusinessDescription: !!comprehensiveData.businessDescription,
        specialtiesFound: comprehensiveData.specialties?.length || 0,
        contentRichness: extractedData.contentAnalysis.dataTypes.length
      };
      
      this.log(`✅ MODERN extraction complete for ${pageType}: ${extractedData.contentAnalysis.dataTypes.length} data types`);
      this.log(`   📋 Menu items: ${comprehensiveData.menuItems?.length || 0}`);
      this.log(`   🛍️ Products: ${comprehensiveData.products?.length || 0}`);
      this.log(`   🔧 Services: ${comprehensiveData.services?.length || 0}`);

    } catch (error) {
      this.log(`⚠️ Modern extraction failed for ${pageType}: ${error.message}`);
      
      // Fallback to basic extraction
      try {
        this.log(`🔄 Attempting basic fallback extraction for ${pageType}...`);
        const basicData = await context.page.extract({
          instruction: `BASIC EXTRACTION - Extract essential business information: company name, contact info, and any menu items or products visible`,
          schema: z.object({
            name: z.string().nullable(),
            phone: z.string().nullable(),
            address: z.string().nullable(),
            email: z.string().nullable(),
            businessContent: z.array(z.string()).nullable(),
            menuItems: z.array(z.object({
              name: z.string(),
              price: z.string().nullable(),
              category: z.string().nullable()
            })).nullable()
          })
        });
        
        Object.assign(extractedData, basicData);
        extractedData.contentAnalysis.dataTypes = Object.keys(basicData).filter(key => basicData[key] !== null);
        this.log(`✅ Basic fallback extraction successful for ${pageType}: ${extractedData.contentAnalysis.dataTypes.length} data types`);
        
      } catch (fallbackError) {
        this.log(`❌ All extraction methods failed for ${pageType}: ${fallbackError.message}`);
        extractedData.error = `Extraction failed: ${error.message}`;
      }
    }

    return extractedData;
  }

  async supplementaryPageDiscovery(baseUrl) {
    this.log(`🔧 Running supplementary page discovery methods...`);
    
    try {
      // Method 1: Check robots.txt and sitemap
      await this.checkRobotsAndSitemap(baseUrl);
      
      // Method 2: Try common patterns as fallback
      await this.tryCommonPatterns(baseUrl);
      
    } catch (error) {
      this.log(`⚠️ Supplementary discovery failed: ${error.message}`);
    }
  }

  async checkRobotsAndSitemap(baseUrl) {
    this.log(`🤖 Checking robots.txt and sitemap for additional URLs...`);
    
    try {
      const robotsUrl = new URL('/robots.txt', baseUrl).href;
      const response = await fetch(robotsUrl);
      
      if (response.ok) {
        const robotsText = await response.text();
        this.log(`✅ Found robots.txt`);
        
        // Look for sitemap URLs
        const sitemapMatches = robotsText.match(/Sitemap:\s*(.+)/gi);
        if (sitemapMatches) {
          for (const match of sitemapMatches) {
            const sitemapUrl = match.replace(/Sitemap:\s*/i, '').trim();
            this.log(`🗺️ Found sitemap: ${sitemapUrl}`);
            
            try {
              const sitemapResponse = await fetch(sitemapUrl);
              if (sitemapResponse.ok) {
                const sitemapContent = await sitemapResponse.text();
                // Parse XML sitemap for additional URLs
                const urlMatches = sitemapContent.match(/<loc>(.*?)<\/loc>/gi);
                if (urlMatches) {
                  this.log(`📍 Found ${urlMatches.length} URLs in sitemap`);
                  // Could add logic to crawl these URLs if needed
                }
              }
            } catch (sitemapError) {
              this.log(`⚠️ Failed to fetch sitemap ${sitemapUrl}: ${sitemapError.message}`);
            }
          }
        }
      }
    } catch (robotsError) {
      this.log(`⚠️ Failed to check robots.txt: ${robotsError.message}`);
    }
  }

  async tryCommonPatterns(baseUrl) {
    this.log(`🔍 Trying common URL patterns as fallback...`);
    
    const patterns = [
      { path: '/menu', type: 'menu' },
      { path: '/about', type: 'about' },
      { path: '/contact', type: 'contact' },
      { path: '/products', type: 'products' },
      { path: '/services', type: 'services' }
    ];

    for (const pattern of patterns) {
      const testUrl = new URL(pattern.path, baseUrl).href;
      try {
        const response = await fetch(testUrl, { method: 'HEAD', timeout: 5000 });
        if (response.ok) {
          this.log(`✅ Found additional page: ${testUrl}`);
          // Could add this to crawl queue if needed
        }
      } catch {
        // Page doesn't exist, continue
      }
    }
  }

  async combineAllPageData(pages, originalUrl) {
    this.log('🔄 Combining COMPREHENSIVE BUSINESS INTELLIGENCE from all crawled pages...');
    
    // Initialize comprehensive combined data structure
    const combined = {
      name: null,
      email: null,
      phone: null,
      address: null,
      
      // Comprehensive business data
      businessIntelligence: {
        menuItems: [],
        products: [],
        services: [],
        companyInfo: {},
        operations: {},
        media: {},
        revenueStreams: [],
        competitiveAdvantages: [],
        businessModel: []
      },
      
      // Legacy fields for backward compatibility
      menuItems: [],
      socialLinks: [],
      openingHours: null,
      restaurantType: null,
      
      // Metadata
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
      allPageNavigation: []
    };

    // Combine data from all pages
    for (const [pageType, pageData] of Object.entries(pages)) {
      if (!pageData || pageData.error) continue;
      
      combined.pagesAnalyzed.push(pageType);
      combined.crawlingStats.successfulExtractions++;
      combined.crawlingStats.contentTypes[pageType] = pageData.contentAnalysis?.dataTypes?.length || 0;

      // Combine basic contact info (prefer non-null values)
      combined.name = combined.name || pageData.name;
      combined.email = combined.email || pageData.email;
      combined.phone = combined.phone || pageData.phone;
      combined.address = combined.address || pageData.address;
      combined.openingHours = combined.openingHours || pageData.hours?.detailed || pageData.hours?.weekday;
      combined.restaurantType = combined.restaurantType || pageData.cuisineType || pageData.restaurantType;

      // MENU DATA - Combine menu items and menu intelligence
      if (pageData.menuItems && pageData.menuItems.length > 0) {
        combined.businessIntelligence.menuItems = combined.businessIntelligence.menuItems.concat(pageData.menuItems);
        combined.menuItems = combined.menuItems.concat(pageData.menuItems); // Legacy compatibility
        combined.crawlingStats.totalMenuItems += pageData.menuItems.length;
        this.log(`📋 Added ${pageData.menuItems.length} menu items from ${pageType} page`);
        
        // Add menu-specific intelligence
        if (pageData.signatureDishes?.length > 0) {
          combined.businessIntelligence.competitiveAdvantages.push(`Signature dishes: ${pageData.signatureDishes.join(', ')}`);
        }
        if (pageData.priceRange) {
          combined.businessIntelligence.businessModel.push(`Menu pricing: ${pageData.priceRange.min} - ${pageData.priceRange.max}`);
        }
      }

      // PRODUCT DATA - Combine products and retail intelligence
      if (pageData.products && pageData.products.length > 0) {
        combined.businessIntelligence.products = combined.businessIntelligence.products.concat(pageData.products);
        combined.crawlingStats.totalProducts += pageData.products.length;
        this.log(`🛍️ Added ${pageData.products.length} products from ${pageType} page`);
        
        // Add product-specific intelligence
        if (pageData.revenueStreams?.length > 0) {
          combined.businessIntelligence.revenueStreams = combined.businessIntelligence.revenueStreams.concat(pageData.revenueStreams);
        }
        if (pageData.ecommerceFeatures?.length > 0) {
          combined.businessIntelligence.businessModel.push(`E-commerce: ${pageData.ecommerceFeatures.join(', ')}`);
        }
      }

      // SERVICES DATA - Combine services and operational intelligence
      if (pageData.services && pageData.services.length > 0) {
        combined.businessIntelligence.services = combined.businessIntelligence.services.concat(pageData.services);
        combined.crawlingStats.totalServices += pageData.services.length;
        this.log(`🔧 Added ${pageData.services.length} services from ${pageType} page`);
        
        // Add service-specific intelligence
        pageData.services.forEach(service => {
          combined.businessIntelligence.revenueStreams.push(service.name);
        });
        
        if (pageData.geographicReach) {
          combined.businessIntelligence.competitiveAdvantages.push(`Geographic reach: ${pageData.geographicReach}`);
        }
      }

      // COMPANY INFO - Combine about/company intelligence
      if (pageType === 'about') {
        combined.businessIntelligence.companyInfo = {
          history: pageData.companyHistory,
          foundingStory: pageData.foundingStory,
          mission: pageData.mission,
          vision: pageData.vision,
          values: pageData.values,
          leadership: pageData.leadership,
          awards: pageData.awards,
          achievements: pageData.achievements,
          uniqueSellingProposition: pageData.uniqueSellingProposition,
          brandPositioning: pageData.brandPositioning
        };
        
        if (pageData.competitiveAdvantages?.length > 0) {
          combined.businessIntelligence.competitiveAdvantages = combined.businessIntelligence.competitiveAdvantages.concat(pageData.competitiveAdvantages);
        }
        
        if (pageData.awards?.length > 0) {
          combined.businessIntelligence.competitiveAdvantages.push(`Awards: ${pageData.awards.length} recognitions`);
        }
        
        this.log(`🏢 Added comprehensive company information from ${pageType} page`);
      }

      // OPERATIONS DATA - Combine operational intelligence
      if (pageType === 'operations') {
        combined.businessIntelligence.operations = {
          hours: pageData.hours,
          locations: pageData.locations,
          capacity: pageData.capacity,
          parking: pageData.parking,
          accessibility: pageData.accessibility,
          operatingModel: pageData.operatingModel
        };
        this.log(`⚙️ Added operational data from ${pageType} page`);
      }

      // MEDIA DATA - Combine marketing and media intelligence
      if (pageType === 'media') {
        combined.businessIntelligence.media = {
          pressContent: pageData.pressMandate,
          awards: pageData.awards,
          testimonials: pageData.testimonials,
          mediaFeatures: pageData.mediaFeatures,
          brandMessaging: pageData.brandMessaging,
          socialProof: pageData.socialProof
        };
        
        if (pageData.awards?.length > 0) {
          combined.businessIntelligence.competitiveAdvantages.push(`Media awards: ${pageData.awards.length} mentions`);
        }
        
        this.log(`📺 Added media and marketing intelligence from ${pageType} page`);
      }

      // SOCIAL LINKS - Backward compatibility
      if (pageData.socialLinks && pageData.socialLinks.length > 0) {
        combined.socialLinks = combined.socialLinks.concat(pageData.socialLinks);
      }

      // BUSINESS CONTENT - General content from any page
      if (pageData.businessContent && pageData.businessContent.length > 0) {
        this.log(`📄 Added general business content from ${pageType} page`);
      }

      // PAGE-SPECIFIC NAVIGATION - Collect navigation from each page
      if (pageData.pageNavigation && pageData.pageNavigation.length > 0) {
        if (!combined.allPageNavigation) {
          combined.allPageNavigation = [];
        }
        
        // Add page context to navigation items
        const contextualNavigation = pageData.pageNavigation.map(nav => ({
          ...nav,
          foundOnPage: pageType,
          foundOnUrl: pageData.url
        }));
        
        combined.allPageNavigation = combined.allPageNavigation.concat(contextualNavigation);
        this.log(`🧭 Added ${pageData.pageNavigation.length} navigation elements from ${pageType} page`);
        
        // Look for page-specific navigation that might lead to new pages
        const pageSpecificLinks = pageData.pageNavigation.filter(nav => nav.pageSpecific);
        if (pageSpecificLinks.length > 0) {
          this.log(`🎯 Found ${pageSpecificLinks.length} page-specific navigation elements on ${pageType}`);
        }
      }
    }

    // Deduplicate arrays
    combined.businessIntelligence.menuItems = this.deduplicateMenuItems(combined.businessIntelligence.menuItems);
    combined.menuItems = this.deduplicateMenuItems(combined.menuItems); // Legacy
    combined.businessIntelligence.revenueStreams = [...new Set(combined.businessIntelligence.revenueStreams)];
    combined.businessIntelligence.competitiveAdvantages = [...new Set(combined.businessIntelligence.competitiveAdvantages)];
    
    // Generate business intelligence summary
    combined.businessIntelligence.summary = this.generateBusinessIntelligenceSummary(combined);
    
    // ENHANCED: Analyze all collected navigation data
    combined.navigationAnalysis = this.analyzeAllNavigationData(combined.allPageNavigation || []);
    
    this.log(`✅ COMPREHENSIVE BUSINESS INTELLIGENCE combined from ${combined.pagesAnalyzed.length} pages:`);
    this.log(`   📋 Menu items: ${combined.crawlingStats.totalMenuItems}`);
    this.log(`   🛍️ Products: ${combined.crawlingStats.totalProducts}`);
    this.log(`   🔧 Services: ${combined.crawlingStats.totalServices}`);
    this.log(`   💰 Revenue streams: ${combined.businessIntelligence.revenueStreams.length}`);
    this.log(`   🎯 Competitive advantages: ${combined.businessIntelligence.competitiveAdvantages.length}`);
    this.log(`   📱 Social platforms: ${combined.socialLinks.length}`);
    this.log(`   🧭 Total navigation elements: ${combined.allPageNavigation?.length || 0}`);
    
    return combined;
  }

  generateBusinessIntelligenceSummary(combinedData) {
    const summary = {
      businessScope: [],
      revenueModel: [],
      marketPosition: [],
      operationalScale: [],
      digitalPresence: []
    };

    const stats = combinedData.crawlingStats;
    
    // Business Scope Analysis
    if (stats.totalMenuItems > 0) {
      summary.businessScope.push(`Food service with ${stats.totalMenuItems} menu items`);
    }
    if (stats.totalProducts > 0) {
      summary.businessScope.push(`Retail products (${stats.totalProducts} items)`);
    }
    if (stats.totalServices > 0) {
      summary.businessScope.push(`Additional services (${stats.totalServices} offerings)`);
    }

    // Revenue Model Analysis
    if (combinedData.businessIntelligence.revenueStreams.length > 0) {
      summary.revenueModel = [`${combinedData.businessIntelligence.revenueStreams.length} revenue streams identified`, ...combinedData.businessIntelligence.revenueStreams.slice(0, 3)];
    }

    // Market Position Analysis
    if (combinedData.businessIntelligence.competitiveAdvantages.length > 0) {
      summary.marketPosition = [`${combinedData.businessIntelligence.competitiveAdvantages.length} competitive advantages`, ...combinedData.businessIntelligence.competitiveAdvantages.slice(0, 2)];
    }

    // Operational Scale
    summary.operationalScale.push(`${stats.totalPagesFound} pages analyzed`);
    summary.operationalScale.push(`${Object.keys(stats.contentTypes).length} content types found`);

    // Digital Presence
    if (combinedData.socialLinks.length > 0) {
      summary.digitalPresence.push(`${combinedData.socialLinks.length} social platforms`);
    }

    return summary;
  }

  deduplicateMenuItems(menuItems) {
    const seen = new Set();
    return menuItems.filter(item => {
      const key = `${item.name}_${item.price}_${item.category}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  resolveUrl(url, baseUrl) {
    try {
      if (url.startsWith('http')) {
        return url; // Already absolute
      }
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
      // Filter out obvious non-URLs first
      if (!url || typeof url !== 'string') return false;
      
      // Filter out javascript, mailto, tel, and anchor links
      if (url.startsWith('javascript:') || 
          url.startsWith('mailto:') || 
          url.startsWith('tel:') || 
          url === '#' || 
          url.startsWith('#')) {
        return false;
      }
      
      // Filter out obvious element IDs or non-URL text
      if (/^\d+$/.test(url)) { // Pure numbers like "1256", "1071"
        // Use debug level logging to reduce noise
        if (process.env.DEBUG) {
          this.log(`⚙️ Debug: Filtering out numeric non-URL: ${url}`);
        }
        return false;
      }
      
      // Must contain path characters or be a valid URL
      if (!url.includes('/') && !url.startsWith('http')) {
        this.log(`⚠️ Filtering out invalid URL format: ${url}`);
        return false;
      }
      
      const urlObj = new URL(url, `https://${hostname}`); // Resolve relative URLs
      
      // Only crawl URLs from the same domain or subdomains
      const isValidDomain = urlObj.hostname === hostname || urlObj.hostname.endsWith(`.${hostname}`);
      
      if (!isValidDomain) {
        this.log(`⚠️ Filtering out external URL: ${url} (${urlObj.hostname} != ${hostname})`);
        return false;
      }
      
      return true;
    } catch (error) {
      this.log(`⚠️ URL validation error for "${url}": ${error.message}`);
      return false;
    }
  }

  async addStealth() {
    this.log('🥷 Adding PRODUCTION-GRADE stealth measures...');
    
    try {
      // PRODUCTION: Get browser and create context with proper spoofing
      const browser = await this.stagehand.browser();
      
      // Randomize viewport for harder fingerprinting
      const baseWidth = 1366;
      const baseHeight = 768;
      const jitterX = Math.floor(Math.random() * 100) - 50; // ±50px
      const jitterY = Math.floor(Math.random() * 100) - 50; // ±50px
      
      const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport: { 
          width: baseWidth + jitterX, 
          height: baseHeight + jitterY 
        },
        // Additional context-level stealth
        extraHTTPHeaders: {
          'Accept-Language': 'en-US,en;q=0.9',
          'Accept-Encoding': 'gzip, deflate, br',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
      });
      
      // HARDENED: Remove webdriver property to defeat detection
      await context.addInitScript(() => {
        // Delete the webdriver property that reveals automation
        delete navigator.__proto__.webdriver;
        
        // Additional hardening
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined,
        });
        
        // Spoof plugins
        Object.defineProperty(navigator, 'plugins', {
          get: () => [1, 2, 3, 4, 5],
        });
      });
      
      // Replace the page with our hardened context page
      await this.stagehand.page.close();
      this.stagehand.page = await context.newPage();
      
      this.log(`✅ PRODUCTION stealth applied: viewport ${baseWidth + jitterX}x${baseHeight + jitterY}, hardened fingerprint`);
    } catch (error) {
      this.log(`⚠️ Failed to apply enhanced stealth measures: ${error.message}`);
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
🕷️  Enhanced Restaurant Website Scraper with Comprehensive Business Intelligence

Usage: node enhanced-scraper.js <url> [--output-file <filename>] [--competitive]

Examples:
  node enhanced-scraper.js https://franklinbarbecue.com
  node enhanced-scraper.js https://example.com --output-file custom-results.json

Features:
  📋 Dynamic page discovery (finds ALL navigation pages)
  🍽️ Comprehensive menu extraction (all meal types, drinks, alcohol)
  🛍️ Product analysis (sauces, rubs, equipment, merchandise)
  🔧 Service offerings (catering, events, delivery)
  🏢 Company intelligence (about, history, awards)
  📊 Complete business intelligence analysis
      `);
      return;
    }

    const url = args[0];
    
    // FIXED: Support for custom output filename to prevent file conflicts
    let outputFilename = null;
    const outFileIndex = args.indexOf('--output-file');
    if (outFileIndex > -1 && args[outFileIndex + 1]) {
      outputFilename = args[outFileIndex + 1];
    }

    if (!url || !url.startsWith('http')) {
      console.error('❌ Please provide a valid URL starting with http:// or https://');
      return;
    }

    try {
      const results = await this.scrapeRestaurant(url);
      
      // Output results summary
      console.log('\n' + '='.repeat(80));
      console.log('📊 COMPREHENSIVE BUSINESS INTELLIGENCE ANALYSIS');
      console.log('='.repeat(80));
      
      if (results.combinedData) {
        const data = results.combinedData;
        const bi = data.businessIntelligence;
        
        // Basic Company Information
        console.log(` Restaurant: ${data.name || 'Name not found'}`);
        console.log(`📍 Address: ${data.address || 'Address not found'}`);
        console.log(`📞 Phone: ${data.phone || 'Phone not found'}`);
        console.log(`📧 Email: ${data.email || 'Email not found'}`);
        
        // Comprehensive Business Analysis
        console.log(`\n📊 BUSINESS SCOPE ANALYSIS:`);
        console.log(`   🍽️  Menu Items: ${data.crawlingStats?.totalMenuItems || 0} items analyzed`);
        console.log(`   🛍️  Products: ${data.crawlingStats?.totalProducts || 0} retail items found`);
        console.log(`   🔧 Services: ${data.crawlingStats?.totalServices || 0} service offerings`);
        console.log(`   💰 Revenue Streams: ${bi?.revenueStreams?.length || 0} identified`);
        
        // Content Analysis
        console.log(`\n📄 CONTENT DISCOVERY:`);
        console.log(`   📋 Pages Crawled: ${data.pagesAnalyzed?.length || 0} (${Object.keys(data.crawlingStats?.contentTypes || {}).join(', ')})`);
        console.log(`   🎯 Competitive Advantages: ${bi?.competitiveAdvantages?.length || 0} identified`);
        console.log(`   📱 Social Platforms: ${data.socialLinks?.length || 0} found`);
        
        // Navigation Analysis
        if (data.navigationAnalysis) {
          console.log(`\n🧭 NAVIGATION ANALYSIS:`);
          console.log(`   📋 Total Navigation Elements: ${data.navigationAnalysis.totalNavigationElements} found across all pages`);
          console.log(`   🔗 Unique URLs: ${data.navigationAnalysis.uniqueUrls} discovered`);
          console.log(`   🎯 Page-Specific Elements: ${data.navigationAnalysis.pageSpecificElements} unique to certain pages`);
          
          if (data.navigationAnalysis.navigationPatterns?.byLocation) {
            const locations = Object.entries(data.navigationAnalysis.navigationPatterns.byLocation);
            if (locations.length > 0) {
              console.log(`   📍 Navigation Locations: ${locations.map(([loc, count]) => `${loc}(${count})`).join(', ')}`);
            }
          }
        }
        
        // Business Intelligence Summary
        if (bi?.summary) {
          console.log(`\n🧠 BUSINESS INTELLIGENCE SUMMARY:`);
          if (bi.summary.businessScope?.length > 0) {
            console.log(`   Scope: ${bi.summary.businessScope.join(', ')}`);
          }
          if (bi.summary.revenueModel?.length > 0) {
            console.log(`   Revenue: ${bi.summary.revenueModel.slice(0, 2).join(', ')}`);
          }
          if (bi.summary.marketPosition?.length > 0) {
            console.log(`   Market: ${bi.summary.marketPosition.slice(0, 2).join(', ')}`);
          }
        }
        
        // Sample Content by Type
        if (bi?.menuItems && bi.menuItems.length > 0) {
          console.log(`\n📋 SAMPLE MENU ITEMS:`);
          bi.menuItems.slice(0, 5).forEach(item => {
            console.log(`   • ${item.name}${item.price ? ` - ${item.price}` : ''}${item.category ? ` (${item.category})` : ''}`);
          });
          if (bi.menuItems.length > 5) {
            console.log(`   ... and ${bi.menuItems.length - 5} more menu items`);
          }
        }
        
        if (bi?.products && bi.products.length > 0) {
          console.log(`\n🛍️  SAMPLE PRODUCTS:`);
          bi.products.slice(0, 3).forEach(product => {
            console.log(`   • ${product.name}${product.price ? ` - ${product.price}` : ''}${product.category ? ` (${product.category})` : ''}`);
          });
          if (bi.products.length > 3) {
            console.log(`   ... and ${bi.products.length - 3} more products`);
          }
        }
        
        if (bi?.services && bi.services.length > 0) {
          console.log(`\n🔧 SAMPLE SERVICES:`);
          bi.services.slice(0, 3).forEach(service => {
            console.log(`   • ${service.name}${service.pricing ? ` - ${service.pricing}` : ''}`);
            if (service.description) {
              console.log(`     ${service.description.substring(0, 60)}...`);
            }
          });
          if (bi.services.length > 3) {
            console.log(`   ... and ${bi.services.length - 3} more services`);
          }
        }
        
        if (bi?.competitiveAdvantages && bi.competitiveAdvantages.length > 0) {
          console.log(`\n🎯 KEY COMPETITIVE ADVANTAGES:`);
          bi.competitiveAdvantages.slice(0, 5).forEach(advantage => {
            console.log(`   • ${advantage}`);
          });
        }
        
        if (bi?.revenueStreams && bi.revenueStreams.length > 0) {
          console.log(`\n💰 REVENUE STREAMS IDENTIFIED:`);
          bi.revenueStreams.slice(0, 5).forEach(stream => {
            console.log(`   • ${stream}`);
          });
        }
        
        // Company Intelligence (if available)
        if (bi?.companyInfo?.mission) {
          console.log(`\n🏢 COMPANY MISSION:`);
          console.log(`   "${bi.companyInfo.mission}"`);
        }
        
        if (bi?.companyInfo?.awards && bi.companyInfo.awards.length > 0) {
          console.log(`\n🏆 AWARDS & RECOGNITION:`);
          bi.companyInfo.awards.slice(0, 3).forEach(award => {
            console.log(`   • ${award}`);
          });
        }
      }
      
      console.log('='.repeat(80));
      
      // Save full results to file
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = outputFilename || `enhanced-scraping-results-${timestamp}.json`;
      
      fs.writeFileSync(filename, JSON.stringify(results, null, 2));
      console.log(`💾 Full results saved to: ${filename}`);
      
      // Log what was saved
      console.log(`\n📁 DATA SAVED:`);
      console.log(`   📄 Complete JSON results: ${filename} (${Math.round(fs.statSync(filename).size / 1024)}KB)`);
      console.log(`   📋 Detailed logs: enhanced-scraper.log`);
      
      // Count and report screenshots
      let totalScreenshots = 0;
      const screenshotPaths = [];
      
      if (results.pages) {
        Object.values(results.pages).forEach(page => {
          if (page.screenshots && page.screenshots.length > 0) {
            totalScreenshots += page.screenshots.length;
            page.screenshots.forEach(screenshot => {
              screenshotPaths.push(screenshot.path);
            });
          }
        });
      }
      
      if (totalScreenshots > 0) {
        console.log(`   📸 Screenshots captured: ${totalScreenshots} images`);
        screenshotPaths.forEach(path => {
          try {
            const size = Math.round(fs.statSync(path).size / (1024 * 1024) * 10) / 10; // MB
            console.log(`      • ${path} (${size}MB)`);
          } catch {
            console.log(`      • ${path} (size unknown)`);
          }
        });
      } else {
        console.log(`   📸 Screenshots: None captured (check logs for errors)`);
      }
      
      console.log(`\n💡 All data persisted for future analysis and proof of crawling!`);
      
    } catch (error) {
      console.error(`💥 Enhanced scraping failed: ${error.message}`);
      process.exit(1);
    }
  }

  analyzeAllNavigationData(allNavigation) {
    this.log(`🔍 Analyzing ${allNavigation.length} navigation elements from all pages...`);
    
    const analysis = {
      totalNavigationElements: allNavigation.length,
      uniqueUrls: new Set(allNavigation.map(nav => nav.url)).size,
      pageSpecificElements: allNavigation.filter(nav => nav.pageSpecific).length,
      navigationByPage: {},
      potentialMissedPages: [],
      navigationPatterns: {}
    };

    // Group navigation by page type
    allNavigation.forEach(nav => {
      if (!analysis.navigationByPage[nav.foundOnPage]) {
        analysis.navigationByPage[nav.foundOnPage] = [];
      }
      analysis.navigationByPage[nav.foundOnPage].push(nav);
    });

    // Identify potential missed pages (navigation elements we haven't crawled)
    allNavigation.forEach(nav => {
      // Look for patterns that suggest we might have missed important pages
      if (nav.pageSpecific) {
        analysis.potentialMissedPages.push({
          url: nav.url,
          text: nav.text,
          foundOnPage: nav.foundOnPage,
          reason: 'Page-specific navigation element'
        });
      }
    });

    // Analyze navigation patterns
    const locations = {};
    const textPatterns = {};
    
    allNavigation.forEach(nav => {
      // Count navigation locations
      locations[nav.location] = (locations[nav.location] || 0) + 1;
      
      // Analyze text patterns
      const lowerText = nav.text.toLowerCase();
      if (lowerText.includes('menu')) textPatterns.menu = (textPatterns.menu || 0) + 1;
      if (lowerText.includes('shop') || lowerText.includes('store')) textPatterns.retail = (textPatterns.retail || 0) + 1;
      if (lowerText.includes('about')) textPatterns.about = (textPatterns.about || 0) + 1;
    });

    analysis.navigationPatterns = {
      byLocation: locations,
      byContent: textPatterns
    };

    this.log(`📊 Navigation analysis: ${analysis.uniqueUrls} unique URLs, ${analysis.pageSpecificElements} page-specific elements`);
    
    return analysis;
  }

  async processJsonEndpoints(results) {
    this.log(`🔍 Analyzing captured JSON endpoints for menu and product data...`);
    
    for (const endpoint of this.jsonEndpoints) {
      try {
        this.log(`   📡 Processing JSON from: ${endpoint.url}`);
        
        // Try to extract menu-like data from JSON structure
        const extractedItems = this.extractMenuItemsFromJson(endpoint.data);
        
        if (extractedItems.menuItems.length > 0 || extractedItems.products.length > 0) {
          // Create a virtual page for this JSON data
          const jsonPageData = {
            url: endpoint.url,
            pageType: 'api_json',
            scrapedAt: new Date(endpoint.timestamp).toISOString(),
            menuItems: extractedItems.menuItems,
            products: extractedItems.products,
            source: 'json_endpoint',
            contentAnalysis: {
              extractionStrategy: 'json_parsing',
              dataTypes: ['menuItems', 'products'].filter(type => extractedItems[type].length > 0),
              businessIntelligence: {
                menuItemsFound: extractedItems.menuItems.length,
                productsFound: extractedItems.products.length
              }
            }
          };
          
          results.pages[`json_${Date.now()}`] = jsonPageData;
          this.log(`   ✅ Extracted ${extractedItems.menuItems.length} menu items and ${extractedItems.products.length} products from JSON`);
        } else {
          this.log(`   ⚠️ No recognizable menu data found in JSON from ${endpoint.url}`);
        }
        
      } catch (error) {
        this.log(`   ❌ Failed to process JSON from ${endpoint.url}: ${error.message}`);
      }
    }
  }

  extractMenuItemsFromJson(data) {
    const menuItems = [];
    const products = [];
    
    // Recursive function to search for menu-like objects in JSON
    const searchForMenuItems = (obj, path = '') => {
      if (!obj || typeof obj !== 'object') return;
      
      if (Array.isArray(obj)) {
        obj.forEach((item, index) => searchForMenuItems(item, `${path}[${index}]`));
        return;
      }
      
      // Look for objects that look like menu items
      const hasMenuFields = obj.name || obj.title || obj.itemName;
      const hasPrice = obj.price || obj.cost || obj.amount;
      const hasDescription = obj.description || obj.desc;
      
      if (hasMenuFields && (hasPrice || hasDescription)) {
        const menuItem = {
          name: obj.name || obj.title || obj.itemName || 'Unknown Item',
          price: obj.price || obj.cost || obj.amount || null,
          description: obj.description || obj.desc || null,
          category: obj.category || obj.type || obj.section || null
        };
        
        // Determine if this looks more like a menu item or product
        const isProduct = path.toLowerCase().includes('product') || 
                         obj.category?.toLowerCase().includes('product') ||
                         obj.type?.toLowerCase().includes('product');
        
        if (isProduct) {
          products.push({
            name: menuItem.name,
            price: menuItem.price,
            description: menuItem.description,
            category: menuItem.category
          });
        } else {
          menuItems.push(menuItem);
        }
      }
      
      // Recursively search all properties
      Object.keys(obj).forEach(key => {
        searchForMenuItems(obj[key], `${path}.${key}`);
      });
    };
    
    searchForMenuItems(data);
    
    return { menuItems, products };
  }

  async discoverAllRelevantPages(baseUrl) {
    this.log('🔍 ENHANCED DYNAMIC DISCOVERY - finding ALL navigation...');
    
    const discoveredPages = [];
    const baseUrlObj = new URL(baseUrl);
    
    try {
      // ENHANCED Strategy 1: DYNAMIC HEADER NAVIGATION EXTRACTION
      this.log('📍 ENHANCED Strategy 1: Dynamic header navigation extraction...');
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
        this.log(`🔍 ENHANCED processing ${headerNavigation.headerNavigation.length} header navigation items...`);
        for (const navItem of headerNavigation.headerNavigation) {
          this.log(`   📋 Raw navigation item: "${navItem.text}" -> "${navItem.url}"`);
          
          const fullUrl = this.resolveUrl(navItem.url, baseUrl);
          this.log(`   🔗 Resolved URL: ${fullUrl}`);
          
          if (fullUrl && this.isValidRestaurantUrl(fullUrl, baseUrlObj.hostname)) {
            discoveredPages.push({
              url: fullUrl,
              type: this.determineContentType(navItem.text, fullUrl, navItem.contentType),
              source: 'enhanced_header_navigation',
              confidence: navItem.prominence || 7,
              linkText: navItem.text,
              expectedContent: navItem.contentType
            });
            this.log(`   ✅ ENHANCED added: ${navItem.text} -> ${fullUrl}`);
          } else {
            this.log(`   ❌ ENHANCED filtered: ${navItem.text} -> ${navItem.url} (invalid URL)`);
          }
        }
      } else {
        this.log(`⚠️ ENHANCED: No header navigation found`);
      }

      const uniquePages = this.deduplicatePages(discoveredPages);
      
      const sortedPages = uniquePages
        .sort((a, b) => b.confidence - a.confidence)
        .slice(0, 12);

      this.log(`✅ ENHANCED DISCOVERY complete: ${sortedPages.length} unique pages found`);
      
      sortedPages.forEach(page => {
        this.log(`   📋 ENHANCED ${page.type.toUpperCase()}: ${page.linkText} (confidence: ${page.confidence})`);
      });
      
      return sortedPages;

    } catch (error) {
      this.log(`❌ ENHANCED page discovery failed: ${error.message}`);
      return [];
    }
  }

  determineContentType(linkText, url, suggestedType) {
    const text = linkText.toLowerCase();
    const urlLower = url.toLowerCase();
    
    // ENHANCED content type detection
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
    this.log(`📊 ENHANCED extracting data from ${pageType}: ${url}`);
    
    const extractedData = {
      url: url,
      pageType: pageType,
      scrapedAt: new Date().toISOString(),
      contentAnalysis: {
        extractionStrategy: `enhanced_${pageType}`,
        dataTypes: [],
        businessIntelligence: {}
      },
      screenshots: []
    };

    try {
      // ENHANCED: Take screenshot for visual proof (SMART: only first of each type)
      this.log(`📸 ENHANCED taking screenshot of ${pageType}...`);
      const timestamp = Date.now();
      const screenshotPath = `consolidated_screenshots/${pageType}_${timestamp}.png`;
      
      // PRODUCTION: Smart screenshotting - only save first of each page type
      const shouldSaveScreenshot = !this.screenshotsSaved.has(pageType);
      
      if (shouldSaveScreenshot) {
        try {
          const screenshotsDir = path.join(process.cwd(), 'consolidated_screenshots');
          if (!fs.existsSync(screenshotsDir)) {
            fs.mkdirSync(screenshotsDir, { recursive: true });
          }
          
          await this.stagehand.page.screenshot({ 
            path: screenshotPath,
            fullPage: true
          });
          
          const s3Url = await this.uploadScreenshotToS3(screenshotPath, pageType, timestamp);
          
          extractedData.screenshots.push({
            path: screenshotPath,
            s3Url: s3Url,
            timestamp: timestamp,
            pageType: pageType,
            url: url
          });
          
          // Mark this page type as screenshotted
          this.screenshotsSaved.add(pageType);
          
          this.log(`✅ ENHANCED screenshot saved (first of ${pageType}): ${screenshotPath}`);
        } catch (screenshotError) {
          this.log(`⚠️ ENHANCED screenshot failed: ${screenshotError.message}`);
        }
      } else {
        this.log(`🔄 SMART: Skipping screenshot for ${pageType} (already have one) - S3 cost optimization`);
      }

      // ENHANCED: Extract comprehensive business data with page-specific focus
      const comprehensiveInstruction = this.getPageSpecificExtractionInstruction(pageType);
      
      // FIXED: Wait longer for dynamic content to load
      this.log(`⏳ Waiting for dynamic content to fully load...`);
      await this.stagehand.page.waitForTimeout(3000); // Give dynamic content time
      await this.stagehand.page.waitForLoadState('networkidle');
      
      // SIMPLIFIED: Use simpler schema for better extraction success
      const comprehensiveData = await this.stagehand.page.extract({
        instruction: comprehensiveInstruction,
        schema: z.object({
          // SIMPLIFIED: Basic business information
          name: z.string().nullable(),
          phone: z.string().nullable(),
          email: z.string().nullable(),
          address: z.string().nullable(),
          
          // SIMPLIFIED: Core content (reduced complexity)
          menuItems: z.array(z.object({
            name: z.string(),
            price: z.string().nullable(),
            description: z.string().nullable()
          })).nullable(),
          
          products: z.array(z.object({
            name: z.string(),
            price: z.string().nullable(),
            description: z.string().nullable()
          })).nullable(),
          
          services: z.array(z.object({
            name: z.string(),
            description: z.string().nullable()
          })).nullable(),
          
          // SIMPLIFIED: Contact info
          hours: z.string().nullable(),
          socialMedia: z.array(z.string()).nullable(),
          
          // SIMPLIFIED: Business content
          businessDescription: z.string().nullable(),
          specialties: z.array(z.string()).nullable()
        })
      });

      // Merge comprehensive data into extracted data
      Object.assign(extractedData, comprehensiveData);
      extractedData.contentAnalysis.dataTypes = Object.keys(comprehensiveData).filter(key => comprehensiveData[key] !== null);
      
      // Add business intelligence summary
      extractedData.contentAnalysis.businessIntelligence = {
        menuItemsFound: comprehensiveData.menuItems?.length || 0,
        productsFound: comprehensiveData.products?.length || 0,
        servicesFound: comprehensiveData.services?.length || 0,
        hasContact: !!(comprehensiveData.phone || comprehensiveData.email),
        hasHours: !!comprehensiveData.hours,
        hasSocialMedia: comprehensiveData.socialMedia?.length || 0,
        hasBusinessDescription: !!comprehensiveData.businessDescription,
        specialtiesFound: comprehensiveData.specialties?.length || 0,
        contentRichness: extractedData.contentAnalysis.dataTypes.length
      };
      
      this.log(`✅ ENHANCED extraction complete for ${pageType}: ${extractedData.contentAnalysis.dataTypes.length} data types`);
      this.log(`   📋 Menu items: ${comprehensiveData.menuItems?.length || 0}`);
      this.log(`   🛍️ Products: ${comprehensiveData.products?.length || 0}`);
      this.log(`   🔧 Services: ${comprehensiveData.services?.length || 0}`);

    } catch (error) {
      this.log(`⚠️ Enhanced extraction failed for ${pageType}: ${error.message}`);
      
      // Fallback to basic extraction
      try {
        this.log(`🔄 Attempting basic fallback extraction for ${pageType}...`);
        const basicData = await this.stagehand.page.extract({
          instruction: `BASIC EXTRACTION - Extract essential business information: company name, contact info, and any menu items or products visible`,
          schema: z.object({
            name: z.string().nullable(),
            phone: z.string().nullable(),
            address: z.string().nullable(),
            email: z.string().nullable(),
            businessContent: z.array(z.string()).nullable(),
            menuItems: z.array(z.object({
              name: z.string(),
              price: z.string().nullable(),
              category: z.string().nullable()
            })).nullable()
          })
        });
        
        Object.assign(extractedData, basicData);
        extractedData.contentAnalysis.dataTypes = Object.keys(basicData).filter(key => basicData[key] !== null);
        this.log(`✅ Basic fallback extraction successful for ${pageType}: ${extractedData.contentAnalysis.dataTypes.length} data types`);
        
      } catch (fallbackError) {
        this.log(`❌ All extraction methods failed for ${pageType}: ${fallbackError.message}`);
        extractedData.error = `Extraction failed: ${error.message}`;
      }
    }

    return extractedData;
  }

  getPageSpecificExtractionInstruction(pageType) {
    const baseInstruction = `Extract business information from this ${pageType.toUpperCase()} page. Be specific and accurate:`;
    
    switch (pageType) {
      case 'menu':
        return `${baseInstruction}
        
        FIND AND EXTRACT:
        - Restaurant name
        - All menu items with names and prices
        - Food descriptions where available
        - Contact info (phone, email, address)
        - Hours of operation
        - Social media links
        
        Focus on finding actual menu items with prices. Look carefully at the page content.`;
        
      case 'products':
        return `${baseInstruction}
        
        FIND AND EXTRACT:
        - Restaurant/business name
        - All products for sale (sauces, equipment, merchandise)
        - Product names, prices, descriptions
        - Contact information
        - Ordering/shipping information
        
        Focus on retail products and merchandise.`;
        
      case 'services':
        return `${baseInstruction}
        
        FIND AND EXTRACT:
        - Restaurant/business name
        - Catering services offered
        - Event services
        - Delivery/pickup options
        - Service descriptions and pricing
        - Contact information
        
        Focus on services offered beyond just dining.`;
        
      case 'about':
        return `${baseInstruction}
        
        FIND AND EXTRACT:
        - Restaurant/business name
        - Company history and story
        - Specialties and signature dishes
        - Awards or recognition
        - Contact information
        - What makes them unique
        
        Focus on company background and what they're known for.`;
        
      case 'contact':
        return `${baseInstruction}
        
        FIND AND EXTRACT:
        - Restaurant/business name
        - Phone number
        - Email address
        - Physical address
        - Hours of operation
        - Social media links
        - Reservation information
        
        Focus on all ways to contact or visit this business.`;
        
      default:
        return `${baseInstruction}
        
        FIND AND EXTRACT:
        - Restaurant/business name
        - Contact information (phone, email, address)
        - Any menu items or products visible
        - Business description
        - Hours of operation
        - Specialties or features
        
        Extract all useful business information from this page.`;
    }
  }

  extractUsernameFromUrl(url) {
    if (!url) return '';
    
    try {
      const urlObj = new URL(url);
      const pathname = urlObj.pathname;
      
      // Remove leading slash and trailing slash, get the first path segment
      const username = pathname.replace(/^\/+|\/+$/g, '').split('/')[0];
      
      // Clean up common URL patterns
      if (username && username !== '' && username !== 'home' && username !== 'page') {
        return username; // Should return: FranklinBBQ, franklinbarbecue, FranklinBarbecue
      }
      
      return '';
    } catch {
      this.log(`⚠️ Failed to extract username from URL: ${url}`);
      return '';
    }
  }
}

// Export for use in other modules
export default EnhancedRestaurantScraper;

// CLI detection and execution
if (process.argv[1] && process.argv[1].endsWith('enhanced-scraper.js')) {
  console.error('✅ Enhanced CLI execution detected!');
  
  const scraper = new EnhancedRestaurantScraper();
  
  // Call main function for CLI handling
  scraper.main().catch(error => {
    console.error('💥 Enhanced CLI execution failed:', error.message);
    process.exit(1);
  });
} else {
  console.error('ℹ️ Enhanced module imported, not executing CLI');
}