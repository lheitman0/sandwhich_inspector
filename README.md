# 🥪 Sandwich Inspector

**A Visual Quality Control Tool for PDF Processing Pipelines**

The Sandwich Inspector is a Streamlit web application that provides an intuitive interface for inspecting, correcting, and validating the outputs a PDF processing pipeline (Specifically the PB&J repo). It allows you to review extracted tables side-by-side with original PDFs, make manual corrections, and maintain quality control over your document processing workflow.

---

## **What Does It Do?**

- **Process PDFs**: Upload or select PDFs and run them through the PB&J pipeline
- **Visual Review**: See original PDF pages alongside extracted structured data
- **Manual Corrections**: Edit table data directly in an intuitive interface
- **Quality Control**: Approve, flag, or edit each page with a simple workflow
- **JSON Inspection**: View both table format and underlying JSON structure

---

## **Complete Setup Guide**


### **Step 1: Get Your API Keys**

You'll need two API keys:

1. **LlamaParse API Key**
   - Go to [LlamaIndex Cloud](https://cloud.llamaindex.ai/)
   - Sign up/login and get your API key
   - Copy the key (starts with `llx-...`)

2. **OpenAI API Key**
   - Go to [OpenAI Platform](https://platform.openai.com/api-keys)
   - Create an account and get your API key
   - Copy the key (starts with `sk-...`)

### **Step 2: Clone the Repository**

```bash
# Clone this sandwich inspector repository
git clone <your-sandwich-inspector-repo-url>
cd sandwich_inspector

# Clone the required PB&J pipeline
git clone https://github.com/DylanDHubert/peanut_butter_jelly
```

### **Step 3: Set Up Your Environment**

```bash
# Install dependencies
pip install -r requirements_inspector.txt
```

### **Step 4: Configure API Keys**

The PB&J pipeline uses a flexible configuration system. You can configure your API keys in multiple ways:

**Option A: Edit the config.yaml file (Recommended)**
```bash
# Navigate to the PB&J directory and edit the config
cd peanut_butter_jelly
nano config.yaml  # or use your preferred editor
```

Update the config.yaml file with your API keys:
```yaml
# API KEYS
# --------
llamaparse_api_key: "your_llamaparse_api_key_here"
openai_api_key: "your_openai_api_key_here"

# OUTPUT SETTINGS
# --------------
output_base_dir: "processed_documents"
create_timestamped_folders: true
use_premium_mode: true

# OPENAI SETTINGS
# ---------------
openai_model: "gpt-4-turbo"
max_tokens: 6000
```

**Option B: Environment Variables (Secure)**
```bash
export LLAMAPARSE_API_KEY="your_llamaparse_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"
```

**Option C: Create a .env file**
```bash
# Create .env file in the project root
echo "LLAMAPARSE_API_KEY=your_llamaparse_api_key_here" > .env
echo "OPENAI_API_KEY=your_openai_api_key_here" >> .env
```

**Configuration Priority (highest to lowest):**
1. Environment variables
2. config.yaml file  
3. .env file
4. Default values

### **Step 5: Set Up Data Directory**

```bash
# Create data directory for your PDF files
mkdir data

# Add some PDF files to test with
# Copy your PDF files into the data/ directory
cp /path/to/your/pdfs/*.pdf data/
```

### **Step 6: Verify Installation**

```bash
# Use the built-in launcher to check everything
python launch_inspector.py
```


---

## 📖 **How to Use**

### **Starting the Application**

**Method 1: Use the Launcher (Recommended)**
```bash
python launch_inspector.py
```

**Method 2: Direct Launch**
```bash
streamlit run sandwich_inspector_app.py
```

The app will open in your browser at `http://localhost:8501`

### **Basic Workflow**

#### **1. Load a Document**

**From Data Directory:**
- Select a PDF from the dropdown in the sidebar
- Click **"Process"** to run it through the pipeline
- Wait for processing to complete


#### **2. 🔍 Review Pages**

- **Navigate**: Use Previous/Next buttons or jump to specific pages
- **Original PDF**: View on the left side
- **Extracted Data**: Tables and structured data on the right
- **JSON Structure**: See the underlying data format

#### **3. Edit Tables (Optional)**

- Click **"✏️ Add Seasoning (Edit)"** to enter edit mode
- Modify table cells directly
- Add/remove rows using the interface
- Changes are automatically saved

#### **4. 🎛️ Quality Control**

For each page, choose one action:

- **✅ Take a Bite (Approve)**: Mark as correctly processed
- **🚩 Save for Later (Flag)**: Mark for later review
- **💾 Save Recipe (Export)**: Download current results

#### **5. Track Progress**

- **Quality Summary**: See approval/flagged/pending counts
- **Flagged Items**: Quick access to pages needing attention
- **Progress Bar**: Visual completion tracking

#### **6. Final Export**

Click **"🏁 Create Final Output Folder"** to generate:
- **Clean JSON**: Final structured data with your corrections
- **Summary Report**: Comprehensive markdown summary
- **Individual Pages**: Separate files for each page
- **Original PDF**: Copy of the source document

---

##  **Understanding the Output**

### **Processing Output Structure**
```
peanut_butter_jelly/processed_documents/
└── document_name_YYYYMMDD_HHMMSS/
    ├── final_output.json          # Main structured data (your edits)
    ├── inspector_metadata.json    # Review tracking data
    ├── document_metadata.json     # Pipeline processing info
    └── original.pdf              # Source PDF
```

### **Final Export Structure**
```
final_outputs/
└── document_name_final/
    ├── document_name_final.json   # Clean final JSON
    ├── document_name_summary.md   # Complete summary
    ├── document_name.pdf          # Original PDF
    ├── export_report.json         # Export metadata
    └── pages/                     # Individual page files
        ├── page_01_title.md
        ├── page_02_title.md
        └── ...
```

### **JSON Structure**
```json
{
  "document_info": {
    "document_name": "sample_document",
    "total_pages": 5,
    "total_tables": 12,
    "review_status": {
      "approved_pages": 4,
      "flagged_pages": 1
    }
  },
  "pages": [
    {
      "page_id": "page_1",
      "title": "Introduction",
      "summary": "Page summary...",
      "keywords": ["keyword1", "keyword2"],
      "tables": [
        {
          "table_id": "table_1",
          "title": "Financial Data",
          "columns": ["Year", "Revenue", "Profit"],
          "rows": [
            ["2021", "$1M", "$200K"],
            ["2022", "$1.2M", "$250K"]
          ]
        }
      ]
    }
  ]
}
```




*The Sandwich Inspector - Making document processing deliciously reliable.* 