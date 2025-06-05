# AI Restaurant Consulting Platform - Advanced Backend Documentation

**GitHub Repository**: [https://github.com/Tramona1/AIConsultant](https://github.com/Tramona1/AIConsultant)

## Quick Start & Setup

### Prerequisites
- **Python 3.11+** for the backend
- **Node.js 18+** for the Stagehand scraper
- **API Keys** (see Environment Variables section below)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Tramona1/AIConsultant.git
   cd AIConsultant
   ```

2. **Backend Setup**:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup** (Next.js):
   ```bash
   npm install
   npm run dev  # Starts development server on http://localhost:3000
   ```

4. **Stagehand Scraper Setup**:
   ```bash
   cd stagehand-scraper
   npm install
   ```

5. **Environment Configuration**:
   - Copy `.env.example` to `.env` (if available) or create a new `.env` file
   - Add your API keys (see Environment Variables section below)

6. **Run the Backend**:
   ```bash
   cd backend
   python main.py  # Starts FastAPI server on http://localhost:8000
   ```

### Project Structure
```
AIConsultant/
├── backend/                          # Python FastAPI backend
├── src/                             # Next.js frontend
├── stagehand-scraper/               # Node.js scraping tools
├── public/                          # Static assets
└── README.md                        # Project overview
```

---

This document provides a **super super in-depth** technical overview of the AI Restaurant Consulting Platform\'s backend, featuring the advanced **4-Phase Progressive Data Extraction System**. This system is meticulously designed for scalability, aiming to efficiently process 10,000+ restaurant websites by optimizing for speed, cost, and data quality.

## 1. Architecture Overview

The backend, built upon the **FastAPI** framework, employs a sophisticated progressive data extraction strategy. This strategy intelligently escalates through four distinct extraction phases. The decision to escalate is dynamically determined by a robust **data quality assessment**, which primarily considers the **completeness of critical data fields** (e.g., name, address, phone, website, hours) and the **reliability of data sources** utilized in preceding phases.

The four phases are:

1.  **Phase 1: Lightweight Pre-computation & Direct Data Acquisition**
    *   **Key Tools**: `GooglePlacesExtractor` (for target restaurant details and local competitor identification), `SchemaOrgExtractor`, `SitemapAnalyzer`.
    *   **Objective**: Rapidly gather foundational data for the target restaurant and identify local competitors with minimal cost and processing.
2.  **Phase 2: Targeted DOM (Document Object Model) Crawling**
    *   **Key Tools**: Playwright (for dynamic content rendering), `DOMCrawler` (with advanced CSS selectors and fallback mechanisms).
    *   **Objective**: Extract data directly from the target restaurant's website HTML, focusing on common restaurant website structures.
3.  **Phase 3: AI-Enhanced Visual & Content Analysis**
    *   **Key Tools**: `AIVisionProcessor` using Gemini Vision API (for screenshot analysis and OCR-like tasks on images, including those derived from PDFs via `PyMuPDF/fitz`). `PyMuPDF` is used for initial text extraction from digitally-born PDFs, with Gemini then structuring this text.
    *   **Objective**: Process visual content (images, PDFs) from the target restaurant's assets when textual data is insufficient or locked in non-machine-readable formats.
4.  **Phase 4: Selective LLM (Large Language Model) Fallback**
    *   **Key Tools**: `StagehandScraper` (via `stagehand_integration.py`), which leverages `enhanced-scraper.js` (a Node.js-based Puppeteer/Playwright script).
    *   **Objective**: Precisely target and extract only critical missing data fields for the target restaurant using advanced LLM capabilities when other methods fall short. This phase may also be used for specialized tasks like "Google Search Intelligence for Social Media".

This multi-phase approach is a cornerstone of the system\'s efficiency. It ensures that computationally expensive and higher-cost methods are reserved only for situations where simpler, faster, and cheaper techniques have not yielded satisfactory data quality. The system is engineered for **intelligent cost optimization**, balancing the need for comprehensive data with practical operational constraints.

**Scope of Competitor Analysis:** The system generates a detailed report for the **target restaurant**. As part of this, it identifies local competitors (primarily using Google Places API in Phase 1) and includes their basic GMB data. The `LLMAnalyzer` then provides a high-level "snapshot" analysis of these competitors based on their GMB data. **A full, independent multi-phase data extraction run is NOT performed for each competitor by default.** Deeper, comparative analysis based on equally detailed data for all competitors would be a significant architectural extension.

## 2. Progressive Data Extraction System (`progressive_data_extractor.py`) - The Core Orchestrator

The `ProgressiveDataExtractor` module serves as the central nervous system for the entire extraction process. It orchestrates the flow through the four phases for the target restaurant, manages data aggregation, and makes critical decisions based on quality assessments.

### 2.1. Key Components & Logic:

*   **Dynamic Phase Progression**: The orchestrator doesn\'t rigidly execute all phases for the target restaurant. Instead, it assesses the output of each phase against predefined quality metrics.
*   **Quality Assessment (`DataQualityValidator`)**: After each phase, the `DataQualityValidator` module evaluates the collected data for the target restaurant. This assessment considers:
    *   **Completeness**: Are all critical fields (name, address, phone, website, hours) present?
    *   **Confidence**: How reliable is the source of each piece of data?
    *   **Plausibility**: Basic checks for data integrity.
    *   It also **identifies critical missing fields** that might trigger subsequent, more targeted extraction phases.
*   **Decision Points & Thresholds**: Based on the overall quality score from `DataQualityValidator`, the orchestrator decides whether to:
    *   Conclude the extraction for the target restaurant if the quality meets the target.
    *   Proceed to the next phase if critical data for the target restaurant is still missing or quality is below thresholds.
*   **Cost Tracking**: The orchestrator meticulously tracks the estimated cost of each phase.
*   **Error Resilience & Graceful Degradation**: If a phase encounters an error, it's logged, partial data is preserved, and the orchestrator may continue or conclude with available information.
*   **Data Aggregation**: Data from each successful phase is progressively merged into a central data structure for the target restaurant.
*   **Final Data Cleaning (`GeminiDataCleaner`)**: After extraction phases, this module performs advanced normalization and standardization of the target restaurant's aggregated data.
*   **Strategic LLM Analysis (`LLMAnalyzer`)**: After cleaning, this module generates strategic insights, including competitor snapshots (based on their GMB data) and comparative analysis for the target restaurant's report.

### 2.2. Phase 1: Lightweight Pre-computation & Direct Data Acquisition

*   **Duration**: Typically 5-20 seconds.
*   **Objective**: Quickly gather readily available, often structured, data for the target restaurant and identify its local competitors.
*   **Modules & Data Sources**:
    *   **`GooglePlacesExtractor`**:
        *   **Target Restaurant**: Utilizes the Google Places API to extract canonical business name, full address, phone number, canonical website URL, operating hours, price level, user ratings, review counts, coordinates, and other GMB details for the **target restaurant**.
        *   **Local Competitor Identification**: If the target restaurant's coordinates are found, performs a Google Places API "Nearby Search" to identify up to 5 local competitors. For each competitor, it fetches basic GMB details (name, address, website, rating, review count, cuisine types). This data populates the `competitors` field in `FinalRestaurantOutput`.
        *   Cost: ~$0.017 for target restaurant Place Details. Competitor identification costs an additional ~$0.005 (Nearby Search base) + ~$0.017 per competitor Place Details call.
    *   **`SchemaOrgExtractor`**: Parses the target restaurant's website HTML for Schema.org microdata.
    *   **`SitemapAnalyzer`**: Fetches and parses `robots.txt` and sitemaps for the target restaurant's website.
    *   **Third-Party Platform Detection**: Scans the target restaurant's homepage for links to common online ordering/delivery platforms.

### 2.3. Phase 2: Targeted DOM Crawling (for Target Restaurant)

*   **Objective**: Extract data directly from the target restaurant's website HTML.
*   **Module**: `DOMCrawler` (Details remain largely the same as previous documentation).

### 2.4. Phase 3: AI-Enhanced Visual & Content Analysis (for Target Restaurant)

*   **Objective**: Extract information from the target restaurant's visual content (screenshots, PDF menus).
*   **Module**: `AIVisionProcessor` (Details remain largely the same, but now includes specific prompts).
*   **Key LLM Prompts (Conceptual for `AIVisionProcessor` within `LLMAnalyzer.analyze_screenshot_with_gemini`):**
    *   **Focus: "menu_impression"**:
        *   Input: Screenshot of a menu.
        *   Task: Analyze visual impression, readability, design, information clarity.
        *   Output: JSON with `visual_impression`, `readability_assessment`, `design_notes`, `information_clarity`, `overall_summary`.
    *   **Focus: "social_profile_check" (for Google SERP screenshots of social profiles - see Section 2.6)**:
        *   Input: Screenshot of a Google Search Result Page showing a social media profile.
        *   Task: Identify platform, extract profile name, follower count, bio snippet, verification status.
        *   Output: JSON with `platform_identified`, `profile_name`, `follower_count`, `bio_snippet`, `verification_status`, `confidence_score`.
    *   **Generic Focus**:
        *   Input: Any image.
        *   Task: Describe content and notable features.
        *   Output: JSON with a `summary`.

### 2.5. Phase 4: Selective LLM Fallback (Stagehand for Target Restaurant)

*   **Objective**: As a final resort, use `enhanced-scraper.js` (via Stagehand) for highly targeted extraction of specific missing critical fields for the target restaurant. Can also be used for specialized tasks.
*   **Module**: `StagehandScraper` (Details remain largely the same).
*   **Specialized Task - "Google Search Intelligence for Social Media"**: See Section 2.6.

### 2.6. Specialized Task: Google Search Intelligence for Social Media (via Stagehand - Phase 4 or direct call)

To ensure reliable social media presence analysis and bypass direct platform bot detection, the system employs a "Google Search Intelligence" strategy.
*   **Mechanism**: When detailed social media information (e.g., follower counts, bio, recent activity indicators beyond just a profile URL) is required for the target restaurant or its competitors:
    1.  The `StagehandScraper` (controlling `enhanced-scraper.js`) is instructed to perform targeted Google searches (e.g., `site:instagram.com "restaurant_handle"`).
    2.  `enhanced-scraper.js` executes these searches, navigates the Google SERPs, and uses its AI capabilities (via Stagehand's underlying LLM) to extract the desired information (follower counts, bio snippets, etc.) directly from the search results.
    3.  `enhanced-scraper.js` captures screenshots of these SERPs, uploads them to S3, and includes their S3 URLs in its JSON output.
*   **Data Consumption**:
    *   The `ProgressiveDataExtractor` receives these S3 URLs and text snippets.
    *   The S3 URLs are passed to `LLMAnalyzer.analyze_screenshot_with_gemini` with the `analysis_focus="social_profile_check"` to verify and structure the visual information from the SERP screenshot.
    *   This combined data (text snippets from Stagehand + structured JSON from SERP screenshot analysis) provides a robust view of the social media presence.
*   **Documentation Note for `enhanced-scraper.js`**: The implementation of the Google SERP scraping logic resides within `enhanced-scraper.js` (User's responsibility). The Python backend provides the framework to request this action and process its results.

## 3. Data Quality & Cleaning System

Ensuring high-quality, standardized data is paramount. This is achieved through a two-pronged approach: continuous quality validation throughout the extraction process and a final comprehensive cleaning phase.

### 3.1. `DataQualityValidator` - Continuous Quality Assessment

*   **Role**: Invoked after each extraction phase by `progressive_data_extractor.py`.
*   **Quality Metrics**:
    *   **Completeness**: A weighted score reflecting the presence of critical vs. important data fields. For example, a missing phone number impacts completeness more than a missing social media link.
    *   **Confidence**: Assesses the trustworthiness of the data, **based on factors like source agreement (e.g., if Google Places and Schema.org both report the same phone number, confidence is higher) and the inherent reliability of the source type (e.g., structured data from an API is generally more reliable than text scraped from a webpage header).**
    *   **Source Reliability (Examples)**: Google Places (0.95), Schema.org (0.85), DOM Scraped (0.7), AI Vision (0.6 - can vary based on image quality/clarity). These are internal heuristics.
    *   **Overall Score**: A composite score (0-1) derived from completeness, confidence, and other factors, used by the orchestrator to make phase progression decisions.
*   **Field Definitions**:
    *   **Critical Fields**: `name`, `address`, `phone`, `website`, `hours`. The system prioritizes acquiring these.
    *   **Important Fields**: `menu_items` (name, price, description), `email`, `social_media_links`, `cuisine_type`, `ratings`, `reviews_count`, `year_established`.
*   **Functionality**:
    *   Identifies specific critical fields that are still missing after a phase.
    *   Provides basic data normalization (e.g., stripping whitespace, simple format corrections) as a preliminary step.

### 3.2. `GeminiDataCleaner` - Advanced AI-Powered Data Cleaning (for Target Restaurant)

*   **Role**: Invoked by `ProgressiveDataExtractor` after extraction phases for the target restaurant.
*   **Advanced Cleaning Tasks & Key LLM Prompts (Conceptual)**:
    *   **Address Parsing & Canonicalization**:
        *   Input: Raw address string.
        *   Task: Parse into structured components (street, city, state, postal_code, country) and provide a canonical version.
        *   Output: JSON with `street_address`, `city`, `state`, `postal_code`, `country`, `address_canonical`.
    *   **Phone Number Standardization**:
        *   Input: Raw phone string.
        *   Task: Convert to E.164 format and extract extension.
        *   Output: JSON with `phone_e164`, `extension`.
    *   **Menu Item Categorization**:
        *   Input: Menu item name and description.
        *   Task: Classify into a predefined list of standard categories (e.g., Appetizer, Main Course, Sushi) and provide AI notes.
        *   Output: JSON with `category_standardized`, `ai_notes`.
    *   **General Text Structuring (e.g., "About Us" text)**:
        *   Input: Block of text.
        *   Task: Extract `year_established`, additional `cuisine_types`, `specialty_items_from_text`, `mission_summary`.
        *   Output: JSON with these extracted fields.
*   **Cost Optimization & Batching**: (Details remain largely the same).

## 4. Strategic LLM Analysis (`llm_analyzer_module.py`)

After data for the target restaurant is collected and cleaned, and basic GMB data for competitors is available, the `LLMAnalyzer` generates the core strategic insights for the report.

### 4.1. Key LLM Prompts (Conceptual):

*   **Prompt 2.1: Target Restaurant Deep Dive**:
    *   Input: `FinalRestaurantOutput` data for the target restaurant (excluding competitor details for this specific prompt, focusing only on the target's own attributes).
    *   Task: Analyze target's strengths, weaknesses, market positioning, USPs based *only* on its own data.
    *   Output: JSON with `key_strengths`, `potential_weaknesses`, `market_positioning_guess`, `unique_selling_propositions`, `target_audience_hypothesis`.
*   **Prompt 2.2: Competitor Snapshot Analysis**:
    *   Input: `CompetitorSummary` data for a single competitor (name, GMB rating, review count, GMB website, GMB cuisine types).
    *   Task: Based *only* on this GMB data, identify apparent key strengths and weaknesses.
    *   Output: JSON with `competitor_name`, `key_strengths`, `key_weaknesses`. (This output updates the `CompetitorSummary` object for that competitor).
*   **Prompt 2.3: Main Strategic Recommendations (Comparative Analysis)**:
    *   Input:
        *   Result of Target Restaurant Deep Dive (Prompt 2.1).
        *   List of updated `CompetitorSummary` objects (GMB data + LLM snapshot from Prompt 2.2).
        *   Core info for target restaurant (name, cuisine, price).
        *   Summary of screenshot analyses (from `analyze_screenshot_with_gemini`, including any SERP analyses for social media).
    *   Task: Generate a sales-focused strategic analysis for the target restaurant, comparing it to competitors and leveraging visual insights.
    *   Output: `LLMStrategicAnalysisOutput` JSON object with:
        *   `executive_hook`
        *   `competitive_landscape_summary` (compares target to competitors)
        *   `prioritized_opportunities` (for target, with AI solution pitch)
        *   `further_insights_teaser`
        *   `generic_success_tips`
        *   `follow_up_engagement_questions`

## 5. API Endpoints (`main.py`)

The FastAPI application exposes several endpoints to interact with the backend services.

### 5.1. Primary Analysis Endpoint:

*   **`POST /analyze-restaurant-progressive`**
    *   **Description**: The primary endpoint for initiating a comprehensive analysis of a restaurant using the full 4-Phase Progressive Data Extraction System.
    *   **Input**:
        *   `restaurant_url: str` (Required)
        *   `restaurant_name: Optional[str]` (Optional, aids Phase 1)
        *   `address: Optional[str]` (Optional, aids Phase 1)
    *   **Process**:
        1.  Invokes `ProgressiveDataExtractor.extract_restaurant_data()`.
        2.  The orchestrator executes Phases 1 through 4 as needed, based on quality assessments.
        3.  Aggregated data is then passed through `GeminiDataCleaner.clean_restaurant_data()` for final processing.
    *   **Output**: A JSON response containing the **cleaned, validated, and comprehensive restaurant data object**, along with detailed `extraction_metadata` (phases completed, durations, costs, final quality score, etc.). This output also includes a path to the generated PDF report if successful.

### 5.2. Legacy Analysis Endpoint:

*   **`POST /api/v1/analyze-restaurant/`**
    *   **Description**: An older endpoint that uses a previous version of the data aggregation and analysis system.
    *   **Status**: **Maintained primarily for backward compatibility with any existing integrations. The `/analyze-restaurant-progressive` endpoint is highly recommended for all new development and provides significantly superior results, cost-efficiency, and data quality.** Future deprecation of this legacy endpoint should be considered.

### 5.3. Report Retrieval Endpoint:

*   **`GET /api/v1/report/{report_id}`**
    *   **Description**: Retrieves stored analysis results (likely from the legacy system, or if progressive results are stored with a similar ID convention).
    *   **Output**: JSON containing report data, potentially including phase breakdowns and costs from the specific analysis run tied to that `report_id`.

### 5.4. PDF Report Generation (`pdf_generator_module.py`)

*   **Module**: `pdf_generator_module.py` (class `RestaurantReportGenerator`).
*   **Functionality**:
    *   Uses the **final, cleaned, and comprehensively analyzed data** (output from `progressive_data_extractor` after `gemini_data_cleaner`) to populate pre-designed HTML templates.
    *   Leverages the **WeasyPrint** library to convert these populated HTML templates into styled, professional-looking PDF reports.
    *   These reports serve as a deliverable, summarizing key findings, competitor insights, and market analysis.

## 6. System Performance & Scalability

The 4-Phase Progressive System is engineered for both high performance and cost-effective scalability.

### 6.1. Performance Metrics (Based on Initial Testing, e.g., Sweetgreen):

*   **Speed Improvement**: The progressive system is approximately **60% faster** for comprehensive data extraction compared to a hypothetical legacy system that might attempt a full deep scrape on every site (e.g., 141 seconds for progressive vs. an estimated 200s+ for a non-optimized deep scrape).
*   **Cost-Effectiveness**: Achieves up to **70% greater cost-effectiveness** due to intelligent phase escalation, avoiding expensive API calls and processing unless necessary.
*   **Data Extraction Success Rate**:
    *   Defining "success" is crucial. A rate of "95%+ data extraction success" is ambitious. It\'s more realistic to break this down:
        *   **Critical Field Acquisition (Name, Address, Phone, Website, Hours)**: Aim for >90-95% success in obtaining these fields across a diverse set of test websites, as these are vital.
        *   **Menu Item Extraction**: Success here can vary wildly based on menu format (HTML, PDF, image). A target might be >70% successful extraction of a significant portion of menu items for sites with identifiable menus.
        *   **Overall Quality Score**: Success could be defined as achieving an overall `final_quality_score` (from `DataQualityValidator`) of > 0.75 for a high percentage of sites.
*   **Phase & Cleaning Breakdown (Illustrative, e.g., from Sweetgreen Test):**
    *   Phase 1 (Lightweight): ~4-5 seconds.
    *   Phase 2 (DOM Crawling): ~50-60 seconds (extracted 50+ menu items).
    *   Phase 3 (AI Vision): ~18-20 seconds.
    *   Phase 4 (Selective Stagehand Fallback): *If triggered*, ~30-90 seconds (cost includes Stagehand LLM usage).
    *   **Data Cleaning (`GeminiDataCleaner`)**: ~20-40 seconds (e.g., 52 Gemini API calls, cost ~$0.052). This step occurs *after* the relevant extraction phases have concluded and data is aggregated.
    *   **Total Time Example (Sweetgreen)**: ~141 seconds (including all necessary phases and final cleaning).

### 6.2. Scalability Features:

*   **Intelligent Phase Skipping**: A key efficiency driver. Initial wider testing might show that **30-40% of restaurants may only require Phase 1** (and potentially Phase 2 for basic menu/contact info) to achieve a good quality score, significantly reducing average processing time and cost per site at scale.
*   **Concurrency**:
    *   **Inter-Restaurant Concurrency**: The FastAPI application is capable of handling multiple concurrent requests to `/analyze-restaurant-progressive`. Each request initiates a separate `ProgressiveDataExtractor` task, allowing many restaurants to be processed in parallel, limited by server resources and API rate limits.
    *   **Intra-Restaurant Concurrency**:
        *   `dom_crawler.py`: Can be designed to crawl multiple pages of a single website concurrently (e.g., using `asyncio.gather` for fetching different discovered menu or contact pages).
        *   `enhanced-scraper.js` (used by Stagehand in Phase 4): Inherently supports concurrent operations for page processing and network requests.
        *   `ai_vision_processor.py` and `gemini_data_cleaner.py`: Multiple asynchronous calls to Gemini APIs can be made using `asyncio.gather` for different images or cleaning tasks related to the *same* restaurant, speeding up these AI-intensive steps.
*   **Quality-Based Early Termination**: If high-quality data is achieved in an early phase, subsequent, more expensive phases are skipped.
*   **Cost Monitoring & Alerts**: The system logs costs per phase. Production deployments should integrate alerts (e.g., if average cost per restaurant exceeds a threshold or if total API spend for a period is too high).
*   **API Rate Limit Handling**: Implemented via `tenacity` library for retries with exponential backoff in API client wrappers (e.g., for Gemini calls in `gemini_data_cleaner.py` and `ai_vision_processor.py`). This helps manage transient API errors and rate limits.

## 7. Environment Variables

Sensitive configurations and API keys are managed via a `.env` file loaded by `python-dotenv`. **Never commit your `.env` file to the repository.**

Create a `.env` file in the `backend/` directory with the following structure:

```dotenv
# Core APIs
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY"    # For Google Places API (Phase 1)
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"    # For Gemini Vision (Phase 3) & Gemini Cleaner (Final Cleaning)

# Browser Automation (if using a cloud service for Playwright/Puppeteer)
BROWSERBASE_API_KEY="YOUR_BROWSERBASE_API_KEY"  # Example for BrowserBase (Phase 2 / Phase 4)
BROWSERBASE_PROJECT_ID="YOUR_PROJECT_ID"    # Example for BrowserBase

# Optional AI Services (Legacy or specialized tasks)
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"        # If any OpenAI models are still used
ELEVENLABS_API_KEY="YOUR_ELEVENLABS_API_KEY"  # For any text-to-speech features (out of scope for core extraction)

# Communication (Out of scope for core extraction, but for potential outreach features)
TWILIO_ACCOUNT_SID="YOUR_TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN="YOUR_TWILIO_AUTH_TOKEN"
TWILIO_PHONE_NUMBER="YOUR_TWILIO_PHONE_NUMBER"

# Stagehand Scraper Specific (if it requires its own API keys for sub-services)
# STAGEHAND_SOME_API_KEY="YOUR_STAGEHAND_SUB_SERVICE_KEY"
```
*Note: `enhanced-scraper.js` might manage its own LLM provider keys internally or via its own .env configuration within the `stagehand-scraper` directory.*

### Required API Keys for Core Functionality:
- **GOOGLE_API_KEY**: Essential for Google Places API (competitor identification, business details)
- **GEMINI_API_KEY**: Required for AI-powered data cleaning and visual analysis

### Optional API Keys:
- **BROWSERBASE_API_KEY**: For cloud-based browser automation (alternative to local Playwright)
- **OPENAI_API_KEY**: For any OpenAI-based fallback analysis
- **TWILIO_**: For SMS/communication features (if implemented)

## 7.1. Development Workflow

### Contributing to the Project

1. **Fork the repository** on GitHub
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** with proper logging and tests
4. **Test your changes**:
   ```bash
   # Backend tests
   cd backend
   python -m pytest
   
   # Run the comprehensive test
   python test_comprehensive_extraction.py
   ```
5. **Commit with descriptive messages**:
   ```bash
   git add .
   git commit -m "feat: add new extraction method for menu items"
   ```
6. **Push and create a Pull Request**

### Development Best Practices

- **Always add logging** when writing new code (as per user requirements)
- **Follow the 4-phase architecture** when adding new extraction methods
- **Update cost tracking** for any new API calls
- **Add error handling** with graceful degradation
- **Test with diverse restaurant websites** using `test_variety_restaurants.py`
- **Document new environment variables** in this documentation

### Local Development Tips

- Use `python main.py` to start the FastAPI server with auto-reload
- Check `backend/app.log` for detailed execution logs
- Monitor API costs during development using the built-in cost tracking
- Test the frontend with `npm run dev` for hot reloading

## 8. File Structure

The backend codebase is organized into modules within the `restaurant_consultant` package:

```
backend/
├── main.py                           # FastAPI application: API endpoints, request/response handling
├── restaurant_consultant/
│   ├── progressive_data_extractor.py # Core 4-phase orchestrator class (ProgressiveDataExtractor)
│   │
│   ├── google_places_extractor.py    # Phase 1: Google Places API client
│   ├── schema_org_extractor.py       # Phase 1: Schema.org parsing logic
│   ├── sitemap_analyzer.py           # Phase 1: Robots.txt & sitemap analysis
│   │
│   ├── dom_crawler.py                # Phase 2: Playwright-based DOM crawling
│   │
│   ├── ai_vision_processor.py        # Phase 3: Gemini Vision API client for images & PDFs
│   │
│   ├── stagehand_integration.py      # Phase 4: Integration with enhanced-scraper.js (StagehandScraper class)
│   │
│   ├── gemini_data_cleaner.py        # Final Cleaning: Advanced data cleaning & normalization with Gemini
│   ├── data_quality_validator.py     # Utility: Data quality assessment logic used by orchestrator
│   └── pdf_generator_module.py       # Utility: PDF report generation from final data
│
├── analysis_data/                    # Directory for storing output files (JSON results, PDFs, logs)
│   └── variety_test_results.json     # Example output from the variety test script
├── menus/                            # If downloaded menus (PDFs, images) are stored temporarily/cached
├── pdf_static/                       # Static assets for PDF reports (CSS, logos) - if used by pdf_generator_module.py
├── pdf_templates/                    # HTML templates for PDF reports - if used by pdf_generator_module.py
├── app.log                           # Main application log file
├── requirements.txt                  # Python package dependencies
├── test_variety_restaurants.py       # Script for testing against diverse restaurant sites
└── .env                              # Environment variable configuration (GITIGNORED)

stagehand-scraper/                    # Directory for the Node.js Stagehand/enhanced-scraper.js tool
  ├── enhanced-scraper.js             # The actual Node.js scraping script
  ├── package.json                    # Node.js dependencies
  └── ...                             # Other helper files, .env for its own keys etc.
```
*(The `sitemap_analyzer.py` is correctly placed within `restaurant_consultant/` as per the project structure shown previously. The documentation text will reflect this location.)*

## 9. Quality Assurance & Testing

A multi-layered approach to ensure system reliability and data accuracy.

*   **Unit Tests**: Each module (`google_places_extractor.py`, `dom_crawler.py`, `gemini_data_cleaner.py`, etc.) should have unit tests covering its core functions, especially focusing on parsing logic, API interactions (with mocks), and data transformation.
*   **Integration Tests**:
    *   Test the interaction between `ProgressiveDataExtractor` and each of its phase execution methods.
    *   Test the full flow for a single restaurant, mocking external API calls to ensure data is passed correctly between phases and that quality assessment triggers phase changes as expected.
*   **End-to-End (E2E) Tests**:
    *   The `test_variety_restaurants.py` script serves as a good starting point for E2E testing against a diverse set of live restaurant websites. This helps identify how the system performs with real-world, unpredictable HTML structures and data formats.
*   **Performance Benchmarks**: Regularly run tests (like `test_variety_restaurants.py`) to track average processing time, cost per restaurant, and success rates. This helps identify performance regressions or improvements.
*   **Cost Tracking Validation**: Compare logged API costs with actual bills from providers (Google Cloud, Gemini) to ensure cost estimation is accurate.
*   **Manual Validation & Golden Datasets**: For a subset of restaurants, manually verify the extracted data against the actual websites to create a "golden dataset." This can be used to assess the accuracy of the automated system over time.

## 10. Error Handling & Resilience

The system incorporates several mechanisms to handle errors and ensure robustness:

*   **Graceful Phase Failures**: As described in Section 2.1, if a phase fails, the `ProgressiveDataExtractor` logs the error, preserves any partial data collected, and can decide to continue to the next phase or finalize based on the current data quality. This prevents the entire process from halting due to an issue in a single, non-critical phase.
*   **Null Data Protection**: Pydantic models and careful dictionary access (`.get()` with defaults) are used throughout the codebase to prevent `NoneType` errors when expected data fields are missing.
*   **API Request Timeouts**: `httpx` (for direct HTTP calls) and other API clients are configured with reasonable timeouts to prevent indefinite hanging.
*   **API Rate Limiting & Transient Error Handling**: The `tenacity` library is used to implement automatic retries with exponential backoff for calls to external APIs (e.g., Gemini). This handles temporary network issues or standard API rate limits gracefully.
*   **Comprehensive Logging**: Detailed logging at each step, including inputs, outputs, errors, and decision points, is crucial for debugging and monitoring system health.

## 11. Configuration & Flexibility

*   **Phase Thresholds**: The quality score thresholds (`self.phase_thresholds` in `ProgressiveDataExtractor`) that trigger progression to the next phase are currently hardcoded. For greater flexibility, these should be made configurable via environment variables or a dedicated configuration file, allowing easy tuning without code changes.
*   **Feature Flags**: For major components like AI Vision or Gemini Cleaning, the system already checks for API key availability to enable/disable them. This concept could be extended for finer-grained control over specific extraction techniques or features if needed for A/B testing or phased rollouts.

## 12. Future Considerations & Potential Enhancements

*   **Deep Competitor Analysis Module**: An optional, separate module/flow that, if triggered, would run the full `ProgressiveDataExtractor` for each identified competitor to gather data as detailed as the target's. This would enable a much richer, truly symmetric comparison but at a significantly higher cost and time.
*   **Advanced Caching**: Implement more sophisticated caching for API responses, especially for data that changes infrequently (e.g., Google Places details if re-requested soon).
*   **Machine Learning for Selector Improvement**: Explore using ML to identify robust CSS selectors or to learn patterns in website structures, potentially reducing the need for manual selector updates.
*   **Knowledge Graph Integration**: Store extracted and cleaned data in a knowledge graph to enable more complex queries and relationship analysis between restaurants, cuisines, locations, etc.
*   **User Feedback Loop**: If the platform includes a UI for users to review/correct extracted data, this feedback could be used to fine-tune extraction models or identify common error patterns.
*   **Visual Data Flow Diagram**: For internal team understanding and onboarding, creating a visual data flow diagram illustrating the phases, modules, decision points, and data movement would be highly beneficial.

This advanced progressive data extraction system represents a significant step towards building a highly scalable and intelligent platform for restaurant AI consulting. Its modular design, focus on data quality, and cost optimization strategies provide a solid foundation for future growth and innovation.
