#!/usr/bin/env python3
"""
🥪 Sandwich Inspector App
========================

A Streamlit app for reviewing and editing processed document outputs.
Quality control and manual correction for document processing pipeline results.
"""

import streamlit as st
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
import os
from dataclasses import dataclass
import re
import tempfile
import shutil

from pdf_utils import PDFViewer, get_pdf_page_count
from inspector_config import get_random_message

# Define data structures that were previously from PB&J
@dataclass
class ProcessedTable:
    """Table data structure from processed documents"""
    title: str
    data: List[Dict[str, Any]]
    
@dataclass  
class ProcessedPage:
    """Page data structure from processed documents"""
    title: str
    content: str
    tables: List[ProcessedTable]
    keywords: List[str]
    pdf_page_number: int

# Page config with sandwich theme
st.set_page_config(
    page_title="🥪 Sandwich Inspector",
    page_icon="🥪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for sandwich theme
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #FFD700, #FFA500);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    .quality-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 15px;
        font-size: 0.8rem;
        font-weight: bold;
        margin: 0.25rem;
    }
    .approved { background-color: #90EE90; color: #006400; }
    .flagged { background-color: #FFB6C1; color: #8B0000; }
    .pending { background-color: #FFE4B5; color: #8B4513; }
    .page-nav {
        background-color: #F5F5DC;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def natural_sort_key(filename):
    """
    Natural sorting key for proper page ordering.
    Returns a tuple that sorts correctly: (page_number, original_name)
    """
    match = re.search(r'page_(\d+)', str(filename))
    page_num = int(match.group(1)) if match else 999999
    return (page_num, str(filename))

def extract_page_number(filename):
    """
    Extract page number from filename.
    Returns page number as integer, or None if not found.
    """
    match = re.search(r'page_(\d+)', str(filename))
    return int(match.group(1)) if match else None

def create_missing_page_placeholder(page_num):
    """
    Create a placeholder ProcessedPage for missing pages.
    """
    return ProcessedPage(
        title=f"❌ Missing Data - Page {page_num}",
        content=f"""# Missing Page Data

⚠️ **This page was not processed by the extraction pipeline.**

**Page Number:** {page_num}

## Possible Reasons:
- Processing pipeline failed on this page
- Complex page layout that couldn't be parsed
- Image-only content with no extractable data
- PDF corruption or technical issues

## Next Steps:
1. 🔄 **Reprocess** this page individually
2. 🔍 **Manual review** of the original PDF
3. 🚩 **Flag for attention** during quality control

---
*This is an automatically generated placeholder for missing page data.*
""",
        tables=[],
        keywords=["missing", "unprocessed", "needs_attention", "placeholder"],
        pdf_page_number=page_num  # Track the actual PDF page this represents
    )

def create_placeholder_json_file(page_num, json_folder):
    """
    Create a placeholder JSON file for a missing page.
    """
    placeholder_data = {
        "title": f"❌ Missing Data - Page {page_num}",
        "page_number": page_num,
        "content": "No data found - this page was not processed by the extraction pipeline.",
        "tables": [],
        "keywords": ["missing", "unprocessed", "needs_attention", "placeholder"],
        "metadata": {
            "status": "missing",
            "reason": "Page not processed by extraction pipeline",
            "created_by": "inspector_placeholder_generator",
            "created_at": datetime.now().isoformat(),
            "needs_reprocessing": True
        },
        "raw_content": "",
        "processing_notes": [
            "This is an automatically generated placeholder",
            "Original page data was not found in processed files",
            "Page needs to be reprocessed by the extraction pipeline"
        ]
    }
    
    json_file_path = json_folder / f"page_{page_num}.json"
    try:
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(placeholder_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.warning(f"Could not create placeholder JSON for page {page_num}: {e}")
        return False

def create_placeholder_markdown_file(page_num, markdown_folder):
    """
    Create a placeholder markdown file for a missing page.
    """
    placeholder_content = f"""# ❌ Missing Page Data - Page {page_num}

> **⚠️ WARNING:** This page was not processed by the extraction pipeline.

## Page Information
- **Page Number:** {page_num}
- **Status:** Missing/Unprocessed
- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Possible Reasons for Missing Data

1. **🔧 Processing Pipeline Failure**
   - Technical error during page processing
   - Pipeline crashed or timed out on this page

2. **📄 Complex Page Layout**
   - Unusual formatting that couldn't be parsed
   - Complex nested tables or graphics
   - Rotated or skewed content

3. **🖼️ Image-Only Content**
   - Page contains only images with no extractable text
   - Scanned document with poor OCR results

4. **💾 PDF Issues**
   - Corrupted PDF data for this page
   - Encrypted or protected content
   - Unsupported PDF features

## Next Steps

### For Data Processing Team:
- [ ] **Reprocess this page individually**
- [ ] **Check pipeline logs for errors**
- [ ] **Verify PDF integrity for this page**
- [ ] **Consider manual extraction if automated processing fails**

### For Quality Control:
- [ ] **Review original PDF page manually**
- [ ] **Determine if page contains important data**
- [ ] **Flag for priority reprocessing if critical**

---

*This placeholder was automatically generated by the Document Inspector.*  
*Replace this file once the page has been successfully processed.*
"""
    
    md_file_path = markdown_folder / f"page_{page_num}.md"
    try:
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(placeholder_content)
        return True
    except Exception as e:
        st.warning(f"Could not create placeholder markdown for page {page_num}: {e}")
        return False

class SandwichInspector:
    """Main application class for the Sandwich Inspector"""
    
    def __init__(self):
        self.init_session_state()
        
    def init_session_state(self):
        """Initialize session state variables"""
        if 'current_document' not in st.session_state:
            st.session_state.current_document = None
        if 'current_page_idx' not in st.session_state:
            st.session_state.current_page_idx = 0
        if 'processed_pages' not in st.session_state:
            st.session_state.processed_pages = []
        if 'page_statuses' not in st.session_state:
            st.session_state.page_statuses = {}
        if 'flagged_pages' not in st.session_state:
            st.session_state.flagged_pages = set()
        if 'document_folder' not in st.session_state:
            st.session_state.document_folder = None
        if 'edit_mode' not in st.session_state:
            st.session_state.edit_mode = False
        if 'missing_pages' not in st.session_state:
            st.session_state.missing_pages = []
        if 'incomplete_pages' not in st.session_state:
            st.session_state.incomplete_pages = []
        if 'useless_pages' not in st.session_state:
            st.session_state.useless_pages = []

    def render_header(self):
        """Render the main header"""
        st.markdown("""
        <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #667eea, #764ba2); color: white; border-radius: 10px; margin-bottom: 30px;">
            <h1 style="margin: 0; font-size: 2.5em;">🔍 Document Accuracy Inspector</h1>
            <p style="margin: 10px 0 0 0; font-size: 1.2em;">Verify extracted data against original PDFs</p>
        </div>
        """, unsafe_allow_html=True)

    def _get_completion_status(self, folder, final_folders):
        """
        Determine completion status of a document folder.
        
        Returns:
            'completed' - Has been exported to final folder
            'in_progress' - Has inspector metadata (been worked on)
            'pending' - Not started yet
        """
        folder_path = str(folder)  # Full path to this processed document
        
        # Check if there's a corresponding final folder by looking at document metadata
        # This is much more accurate than name-based matching
        for final_folder_name in final_folders:
            final_folder_path = Path(".") / final_folder_name
            metadata_file = final_folder_path / "document_metadata.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Check if this final folder corresponds to our processed document
                    main_folder = metadata.get('folder_structure', {}).get('main_folder', '')
                    if main_folder and folder_path.endswith(main_folder.split('/')[-1]):
                        return "completed"
                except Exception:
                    # If we can't read metadata, continue to next final folder
                    continue
        
        # Check if there's inspector metadata (indicates work in progress)
        metadata_file = folder / "inspector_metadata.json"
        if metadata_file.exists():
            return "in_progress"
        
        # Check if any pages have been approved (another sign of work in progress)
        # Look for any edited files that are newer than the original processing
        json_folder = folder / "03_cleaned_json"
        if json_folder.exists():
            try:
                # Get the folder creation time as baseline
                folder_time = folder.stat().st_mtime
                for json_file in json_folder.glob("*.json"):
                    if json_file.stat().st_mtime > folder_time + 60:  # 1 minute grace period
                        return "in_progress"
            except Exception:
                pass
        
        return "pending"

    def render_sidebar(self):
        """Render the sidebar with navigation and controls"""
        st.sidebar.markdown("## 📁 Processed Documents")
        
        # Get available processed documents from processed_documents directory
        processed_dir = Path("processed_documents")
        if processed_dir.exists():
            # Get all document folders
            document_folders = [d for d in processed_dir.iterdir() if d.is_dir()]
            
            if document_folders:
                # Sort by modification time (newest first)
                document_folders.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # Get all final folders to check completion status
                final_folders = []
                current_dir = Path(".")
                for item in current_dir.iterdir():
                    if item.is_dir() and item.name.startswith("final_"):
                        final_folders.append(item.name)
                
                # Create display names with timestamps and completion status
                folder_options = []
                for folder in document_folders:
                    folder_name = folder.name
                    
                    # Check completion status
                    completion_status = self._get_completion_status(folder, final_folders)
                    
                    # Extract timestamp from folder name if available
                    parts = folder_name.split('_')
                    if len(parts) >= 3:
                        try:
                            date_part = parts[-2]
                            time_part = parts[-1]
                            date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                            time_str = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                            base_name = f"{parts[0]} ({date_str} {time_str})"
                        except (IndexError, ValueError):
                            base_name = folder_name
                    else:
                        base_name = folder_name
                    
                    # Add completion status to display name
                    if completion_status == "completed":
                        display_name = f"✅ {base_name}"
                    elif completion_status == "in_progress":
                        display_name = f"🔄 {base_name}"
                    else:
                        display_name = f"⏳ {base_name}"
                    
                    folder_options.append((display_name, folder))
                
                # Show completion progress summary
                completed_count = sum(1 for display_name, _ in folder_options if display_name.startswith("✅"))
                in_progress_count = sum(1 for display_name, _ in folder_options if display_name.startswith("🔄"))
                pending_count = sum(1 for display_name, _ in folder_options if display_name.startswith("⏳"))
                total_count = len(folder_options)
                
                if total_count > 0:
                    completion_pct = (completed_count / total_count) * 100
                    st.sidebar.markdown("### 📊 Overall Progress")
                    st.sidebar.progress(completion_pct / 100)
                    st.sidebar.markdown(f"""
                    <div style="font-size: 0.9em;">
                    ✅ <strong>Completed:</strong> {completed_count}/{total_count} ({completion_pct:.0f}%)<br>
                    🔄 <strong>In Progress:</strong> {in_progress_count}<br>
                    ⏳ <strong>Pending:</strong> {pending_count}
                    </div>
                    """, unsafe_allow_html=True)
                    st.sidebar.markdown("---")
                
                # Document selection
                selected_option = st.sidebar.selectbox(
                    "Select document to review:",
                    range(len(folder_options)),
                    format_func=lambda i: folder_options[i][0],
                    help="✅ Completed | 🔄 In Progress | ⏳ Pending"
                )
                
                if selected_option is not None:
                    selected_folder = folder_options[selected_option][1]
                    selected_display_name = folder_options[selected_option][0]
                    
                    # Show status-specific button text
                    if selected_display_name.startswith("✅"):
                        button_text = "🔍 Review Completed"
                        button_type = "secondary"
                    elif selected_display_name.startswith("🔄"):
                        button_text = "📖 Continue Review"
                        button_type = "primary"
                    else:
                        button_text = "🚀 Start Review"
                        button_type = "primary"
                    
                    # Load document button
                    if st.sidebar.button(button_text, use_container_width=True, type=button_type):
                        self.load_processed_document(selected_folder)
                    
                    # Show document info if available
                    if selected_folder.exists():
                        metadata_file = selected_folder / "document_metadata.json"
                        if metadata_file.exists():
                            try:
                                with open(metadata_file) as f:
                                    metadata = json.load(f)
                                    st.sidebar.markdown("### 📄 Document Info")
                                    st.sidebar.markdown(f"**Pages:** {metadata.get('total_pages', 'Unknown')}")
                                    if 'pdf_file_size' in metadata:
                                        size_mb = metadata['pdf_file_size'] / (1024 * 1024)
                                        st.sidebar.markdown(f"**Size:** {size_mb:.1f} MB")
                            except Exception:
                                pass
            else:
                st.sidebar.warning("No processed documents found")
                st.sidebar.markdown("Place processed documents in the `processed_documents/` folder")
        else:
            st.sidebar.error("processed_documents/ directory not found")
            if st.sidebar.button("Create processed_documents folder"):
                processed_dir.mkdir(exist_ok=True)
                st.rerun()
        
        st.sidebar.markdown("---")
        
        # Document navigation
        if st.session_state.processed_pages:
            st.sidebar.markdown("## 📖 Recipe Navigation")
            
            total_pages = len(st.session_state.processed_pages)
            current_page = st.session_state.current_page_idx + 1
            
            st.sidebar.markdown(f"**Page {current_page} of {total_pages}**")
            
            # Page navigation buttons
            col1, col2 = st.sidebar.columns(2)
            with col1:
                if st.button("◀️ Previous"):
                    if st.session_state.current_page_idx > 0:
                        st.session_state.current_page_idx -= 1
                        st.rerun()
            
            with col2:
                if st.button("Next ▶️"):
                    if st.session_state.current_page_idx < total_pages - 1:
                        st.session_state.current_page_idx += 1
                        st.rerun()
            
            # Direct page selection with enhanced format
            def format_page_dropdown(page_num):
                # page_num is 1-based, convert to 0-based for array access
                page_index = page_num - 1
                page = st.session_state.processed_pages[page_index]
                pdf_page_num = page.pdf_page_number
                title = page.title
                
                # Check if useless (only from explicit useless_pages list)
                is_useless = pdf_page_num in st.session_state.get('useless_pages', [])
                
                # Check if missing
                is_missing = pdf_page_num in st.session_state.get('missing_pages', [])
                
                # Truncate title
                display_title = title[:25] + "..." if len(title) > 25 else title
                
                if is_useless:
                    return f"🗑️ PDF Page {pdf_page_num}: {display_title}"
                elif is_missing:
                    return f"❌ PDF Page {pdf_page_num}: {display_title}"
                else:
                    return f"📄 PDF Page {pdf_page_num}: {display_title}"
            
            new_page = st.sidebar.selectbox(
                "Jump to page:",
                range(1, total_pages + 1),
                index=current_page - 1,
                format_func=format_page_dropdown
            ) - 1
            
            if new_page != st.session_state.current_page_idx:
                st.session_state.current_page_idx = new_page
                st.rerun()
                
            st.sidebar.markdown("---")
            
            # Quality control summary
            st.sidebar.markdown("## 📊 Quality Summary")
            
            # Clean up page statuses to match current pages
            valid_page_indices = set(range(total_pages))
            st.session_state.page_statuses = {
                k: v for k, v in st.session_state.page_statuses.items() 
                if k in valid_page_indices
            }
            st.session_state.flagged_pages = {
                p for p in st.session_state.flagged_pages 
                if p in valid_page_indices
            }
            
            approved = sum(1 for status in st.session_state.page_statuses.values() if status == 'approved')
            flagged = len(st.session_state.flagged_pages)
            useless = len(st.session_state.get('useless_pages', []))
            pending = max(0, total_pages - approved - flagged - useless)  # Ensure non-negative
            
            st.sidebar.markdown(f"""
            <div class="quality-badge approved">✅ Approved: {approved}</div><br>
            <div class="quality-badge flagged">🚩 Flagged: {flagged}</div><br>
            <div class="quality-badge pending">⏳ Pending: {pending}</div><br>
            <div class="quality-badge" style="background-color: #D3D3D3; color: #666666;">🗑️ Useless: {useless}</div>
            """, unsafe_allow_html=True)
            
            # Missing pages summary
            missing_pages = st.session_state.get('missing_pages', [])
            if missing_pages:
                st.sidebar.markdown("## ❌ Missing Data")
                st.sidebar.error(f"**{len(missing_pages)} pages need attention:**")
                
                # Show missing pages as clickable buttons
                missing_display = []
                for page_num in missing_pages[:6]:  # Show up to 6 missing pages
                    # Find the UI index for this PDF page number
                    ui_index = None
                    for i, page in enumerate(st.session_state.processed_pages):
                        if hasattr(page, 'pdf_page_number') and page.pdf_page_number == page_num:
                            ui_index = i
                            break
                    
                    if ui_index is not None:
                        if st.sidebar.button(f"📄 Page {page_num}", key=f"missing_{page_num}", 
                                           help=f"Jump to missing page {page_num} (UI position {ui_index + 1})",
                                           use_container_width=True):
                            st.session_state.current_page_idx = ui_index
                            st.rerun()
                    else:
                        # Fallback button that doesn't navigate
                        st.sidebar.button(f"📄 Page {page_num} ❌", key=f"missing_err_{page_num}", 
                                        help=f"Missing page {page_num} - not found in loaded pages",
                                        use_container_width=True, disabled=True)
                
                if len(missing_pages) > 6:
                    st.sidebar.markdown(f"*...and {len(missing_pages) - 6} more*")
                    
                st.sidebar.markdown("💡 *These pages show placeholders - check PDF for content*")
            
            # Incomplete pages summary
            incomplete_pages = st.session_state.get('incomplete_pages', [])
            if incomplete_pages:
                st.sidebar.markdown("## ⚠️ Incomplete Processing")
                st.sidebar.warning(f"**{len(incomplete_pages)} pages only partially processed:**")
                
                # Show incomplete pages as clickable buttons
                for page_num in incomplete_pages[:6]:  # Show up to 6 incomplete pages
                    # Find the UI index for this PDF page number
                    ui_index = None
                    for i, page in enumerate(st.session_state.processed_pages):
                        if hasattr(page, 'pdf_page_number') and page.pdf_page_number == page_num:
                            ui_index = i
                            break
                    
                    if ui_index is not None:
                        if st.sidebar.button(f"⚠️ Page {page_num}", key=f"incomplete_{page_num}", 
                                           help=f"Jump to incomplete page {page_num} (UI position {ui_index + 1}) - has markdown but no JSON",
                                           use_container_width=True):
                            st.session_state.current_page_idx = ui_index
                            st.rerun()
                    else:
                        # Fallback button that doesn't navigate
                        st.sidebar.button(f"⚠️ Page {page_num} ❌", key=f"incomplete_err_{page_num}", 
                                        help=f"Incomplete page {page_num} - not found in loaded pages",
                                        use_container_width=True, disabled=True)
                
                if len(incomplete_pages) > 6:
                    st.sidebar.markdown(f"*...and {len(incomplete_pages) - 6} more*")
                    
                st.sidebar.markdown("💡 *These pages have markdown content but processing failed after stage 1*")
                
                # Bulk placeholder file creation
                st.sidebar.markdown("---")
                st.sidebar.markdown("### 📁 Create Placeholder Files")
                st.sidebar.markdown("Generate actual JSON and markdown files for missing pages:")
                
                if st.sidebar.button("🔧 Create All Placeholder Files", 
                                   key="create_all_placeholders",
                                   help=f"Create placeholder JSON and markdown files for all {len(missing_pages)} missing pages",
                                   use_container_width=True):
                    
                    if st.session_state.document_folder:
                        json_folder = st.session_state.document_folder / "03_cleaned_json"
                        markdown_folder = st.session_state.document_folder / "01_parsed_markdown"
                        
                        # Ensure directories exist
                        json_folder.mkdir(exist_ok=True)
                        markdown_folder.mkdir(exist_ok=True)
                        
                        success_count = 0
                        json_success = 0
                        md_success = 0
                        
                        progress_bar = st.sidebar.progress(0)
                        status_text = st.sidebar.empty()
                        
                        for i, page_num in enumerate(missing_pages):
                            progress = (i + 1) / len(missing_pages)
                            progress_bar.progress(progress)
                            status_text.text(f"Creating files for page {page_num}...")
                            
                            json_created = create_placeholder_json_file(page_num, json_folder)
                            md_created = create_placeholder_markdown_file(page_num, markdown_folder)
                            
                            if json_created:
                                json_success += 1
                            if md_created:
                                md_success += 1
                            if json_created and md_created:
                                success_count += 1
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        if success_count == len(missing_pages):
                            st.sidebar.success(f"✅ Created placeholder files for all {success_count} missing pages!")
                        else:
                            st.sidebar.warning(f"⚠️ Created files for {success_count}/{len(missing_pages)} pages")
                            st.sidebar.markdown(f"JSON files: {json_success}/{len(missing_pages)}")
                            st.sidebar.markdown(f"Markdown files: {md_success}/{len(missing_pages)}")
                        
                        if success_count > 0:
                            st.sidebar.info("💡 Reload the document to see the placeholder files integrated")
                    else:
                        st.sidebar.error("❌ No document folder available")
            
            # Useless pages summary
            useless_pages = st.session_state.get('useless_pages', [])
            if useless_pages:
                st.sidebar.markdown("## 🗑️ Useless Pages")
                st.sidebar.info(f"**{len(useless_pages)} pages marked as useless:**")
                
                # Show useless pages as clickable buttons
                for page_num in useless_pages[:6]:  # Show up to 6 useless pages
                    # Find the UI index for this PDF page number
                    ui_index = None
                    for i, page in enumerate(st.session_state.processed_pages):
                        if hasattr(page, 'pdf_page_number') and page.pdf_page_number == page_num:
                            ui_index = i
                            break
                    
                    if ui_index is not None:
                        if st.sidebar.button(f"🗑️ Page {page_num}", key=f"useless_{page_num}", 
                                           help=f"Jump to useless page {page_num} (UI position {ui_index + 1})",
                                           use_container_width=True):
                            st.session_state.current_page_idx = ui_index
                            st.rerun()
                    else:
                        # Fallback button that doesn't navigate
                        st.sidebar.button(f"🗑️ Page {page_num} ❌", key=f"useless_err_{page_num}", 
                                        help=f"Useless page {page_num} - not found in loaded pages",
                                        use_container_width=True, disabled=True)
                
                if len(useless_pages) > 6:
                    st.sidebar.markdown(f"*...and {len(useless_pages) - 6} more*")
                    
                st.sidebar.markdown("💡 *These pages contain only 'useless' placeholder content*")
            
            # Flagged items review
            if st.session_state.flagged_pages:
                st.sidebar.markdown("## 🚩 Items to Review")
                for page_idx in sorted(st.session_state.flagged_pages):
                    page_title = st.session_state.processed_pages[page_idx].title
                    if st.sidebar.button(f"📄 Page {page_idx + 1}: {page_title[:20]}..."):
                        st.session_state.current_page_idx = page_idx
                        st.rerun()
            
            st.sidebar.markdown("---")
            
            # Portfolio tagging section
            st.sidebar.markdown("## 🏷️ Portfolio Tag")
            
            # Initialize portfolio tag if not set
            if 'portfolio_tag' not in st.session_state:
                st.session_state.portfolio_tag = None
            
            # Portfolio selection
            portfolio_options = ["ts knee", "knee", "hips"]
            selected_portfolio = st.sidebar.selectbox(
                "Select portfolio category:",
                [None] + portfolio_options,
                index=0 if st.session_state.portfolio_tag is None else portfolio_options.index(st.session_state.portfolio_tag) + 1,
                format_func=lambda x: "Select category..." if x is None else x,
                help="Categorize this document for portfolio organization"
            )
            
            # Update session state when selection changes
            if selected_portfolio != st.session_state.portfolio_tag:
                st.session_state.portfolio_tag = selected_portfolio
                # Save the tag immediately
                if st.session_state.document_folder:
                    self.save_portfolio_tag()
                    if selected_portfolio:
                        st.sidebar.success(f"✅ Tagged as: {selected_portfolio}")
            
            if st.session_state.portfolio_tag:
                st.sidebar.markdown(f"**Current tag:** `{st.session_state.portfolio_tag}`")
            
            st.sidebar.markdown("---")
            
            # Final export section
            st.sidebar.markdown("## 🏁 Final Export")
            
            # Show completion progress
            completion_pct = ((approved + flagged) / total_pages * 100) if total_pages > 0 else 0
            completion_pct = min(100.0, completion_pct)  # Cap at 100%
            progress_value = completion_pct / 100
            progress_value = max(0.0, min(1.0, progress_value))  # Ensure valid range [0.0, 1.0]
            
            st.sidebar.progress(progress_value)
            st.sidebar.markdown(f"**Review Progress:** {completion_pct:.1f}%")
            
            if st.sidebar.button("🏁 Create Final Output Folder", 
                               use_container_width=True,
                               help="Create a clean final output folder with all your reviewed content"):
                self.create_final_output_folder()
            
            st.sidebar.markdown("*Creates a clean folder with your final JSON, markdown summary, and original PDF*")

    def load_processed_document(self, document_folder):
        """Load a processed document from the processed_documents folder"""
        try:
            # Check if the folder has the expected structure
            # We use PARSED markdown (01_parsed_markdown) NOT enhanced markdown (02_enhanced_markdown)
            json_folder = document_folder / "03_cleaned_json"
            markdown_folder = document_folder / "01_parsed_markdown"
            
            # Check for the new final_output.json structure first
            final_output_file = document_folder / "final_output.json"
            
            if final_output_file.exists():
                # Load from new consolidated JSON structure
                self._load_from_final_output(document_folder, final_output_file)
            elif json_folder.exists() and markdown_folder.exists():
                # Fallback to old individual file structure for backward compatibility
                self._load_from_individual_files(document_folder, json_folder, markdown_folder)
            else:
                st.error(f"❌ Invalid document structure in {document_folder.name}")
                st.error("Expected either 'final_output.json' or '03_cleaned_json/' folder")
                return
                
        except Exception as e:
            st.error(f"❌ Error loading document: {e}")

    def _load_from_final_output(self, document_folder, final_output_file):
        """Load document from new final_output.json structure"""
        try:
            with open(final_output_file, 'r') as f:
                final_data = json.load(f)
            
            # Get PDF page count for comparison
            folder_name = document_folder.name
            doc_name = folder_name.split('_')[0]
            pdf_path = document_folder / f"{doc_name}.pdf"
            
            total_pdf_pages = 0
            if pdf_path.exists():
                total_pdf_pages = get_pdf_page_count(pdf_path)
                st.info(f"📄 PDF has {total_pdf_pages} pages")
            
            # Extract pages from the new structure
            pages_data = final_data.get('pages', [])
            if not pages_data:
                st.error("❌ No pages found in final_output.json")
                return
            
            processed_data_by_page = {}
            
            # Map existing processed pages by their page numbers
            for i, page_data in enumerate(pages_data):
                # Try to extract page number from various sources
                page_num = i + 1  # Default fallback
                
                # Try to get from page_id if available
                if 'page_id' in page_data:
                    match = re.search(r'page_(\d+)', page_data['page_id'])
                    if match:
                        page_num = int(match.group(1))
                elif 'page_number' in page_data:
                    page_num = page_data['page_number']
                
                processed_data_by_page[page_num] = page_data
            
            # Determine page range - use PDF page count if available
            if total_pdf_pages > 0:
                page_range = range(1, total_pdf_pages + 1)
                st.info(f"🎯 Using PDF page count: pages 1-{total_pdf_pages}")
            else:
                # Fallback to processed data range
                max_page = max(processed_data_by_page.keys()) if processed_data_by_page else len(pages_data)
                page_range = range(1, max_page + 1)
                st.info(f"📊 Using processed data range: pages 1-{max_page}")
            
            # Track missing pages
            missing_pages = []
            processed_pages = []
            
            # Process each page in order
            for page_num in page_range:
                if page_num in processed_data_by_page:
                    # Page has processed data - load it normally
                    try:
                        page_data = processed_data_by_page[page_num]
                        
                        # SMART CONTENT SELECTION: Check if document has been edited/reviewed
                        has_been_edited = self._document_has_been_edited(document_folder)
                        
                        if has_been_edited:
                            # EDITED DOCUMENT: Respect user edits in final_output.json (including "useless" markings)
                            page_content = page_data.get('raw_content', page_data.get('content', ''))
                            print(f"✅ Using final_output.json content for page {page_num} (edited document)")
                        else:
                            # UNEDITED DOCUMENT: Use clean original markdown, fallback to final_output.json
                            page_content = ""
                            markdown_folder = document_folder / "01_parsed_markdown"
                            if markdown_folder.exists():
                                markdown_file = markdown_folder / f"page_{page_num}.md"
                                if markdown_file.exists():
                                    try:
                                        with open(markdown_file, 'r', encoding='utf-8') as f:
                                            page_content = f.read()
                                        print(f"✅ Using original markdown for page {page_num} (unedited document)")
                                    except Exception as e:
                                        print(f"❌ Error loading parsed markdown: {e}")
                                        page_content = page_data.get('raw_content', page_data.get('content', ''))
                                else:
                                    print(f"⚠️ Parsed markdown not found, using final_output.json for page {page_num}")
                                    page_content = page_data.get('raw_content', page_data.get('content', ''))
                            else:
                                print(f"⚠️ Parsed markdown folder not found, using final_output.json for page {page_num}")
                                page_content = page_data.get('raw_content', page_data.get('content', ''))
                        
                        # Create ProcessedTable objects from new structure
                        tables = []
                        tables_data = page_data.get('tables', [])
                        
                        if tables_data and isinstance(tables_data, list):
                            for table_data in tables_data:
                                if isinstance(table_data, dict):
                                    # Handle new "rows" format (objects with column names as keys)
                                    rows = table_data.get('rows', [])
                                    
                                    if rows and isinstance(rows, list) and len(rows) > 0:
                                        # Convert rows format to the data format expected by our UI
                                        # rows: [{"Column A": "value1", "Column B": "value2"}, ...]
                                        # becomes data: [{"Column A": "value1", "Column B": "value2"}, ...]
                                        # (actually the format is already compatible!)
                                        
                                        table = ProcessedTable(
                                            title=table_data.get('title', table_data.get('table_id', 'Untitled Table')),
                                            data=rows  # rows format is already compatible with our UI
                                        )
                                        tables.append(table)
                        
                        # Create ProcessedPage object
                        page = ProcessedPage(
                            title=page_data.get('title', f'Page {page_num}'),
                            content=page_content,
                            tables=tables,
                            keywords=page_data.get('keywords', []),
                            pdf_page_number=page_num
                        )
                        processed_pages.append(page)
                        
                    except Exception as e:
                        st.error(f"❌ Error loading page {page_num}: {e}")
                        processed_pages.append(create_missing_page_placeholder(page_num))
                        missing_pages.append(page_num)
                        
                else:
                    # Page is missing - create placeholder
                    st.warning(f"⚠️ Missing data for page {page_num}")
                    processed_pages.append(create_missing_page_placeholder(page_num))
                    missing_pages.append(page_num)
            
            if processed_pages:
                # Store missing pages info in session state
                st.session_state.missing_pages = missing_pages
                
                # Display summary
                if missing_pages:
                    st.warning(f"⚠️ {len(missing_pages)} pages have missing data: {', '.join(map(str, missing_pages))}")
                
                st.success(f"✅ Loaded {len(processed_pages)} pages with proper PDF alignment")
                self._finalize_document_loading(document_folder, processed_pages)
            else:
                st.error("❌ No pages could be loaded from the document")
                
        except Exception as e:
            st.error(f"❌ Error reading final_output.json: {e}")

    def _load_from_individual_files(self, document_folder, json_folder, markdown_folder):
        """Load document from old individual file structure with page number matching"""
        try:
            # Get PDF page count for proper alignment
            folder_name = document_folder.name
            doc_name = folder_name.split('_')[0]
            pdf_path = document_folder / f"{doc_name}.pdf"
            
            total_pdf_pages = 0
            if pdf_path.exists():
                total_pdf_pages = get_pdf_page_count(pdf_path)
                st.info(f"📄 PDF has {total_pdf_pages} pages")
            else:
                st.warning(f"⚠️ PDF not found: {pdf_path.name}. Using file-based page detection.")
            
            # Get all JSON and markdown files
            json_files = list(json_folder.glob("page_*.json"))
            markdown_files = list(markdown_folder.glob("page_*.md"))
            
            if not json_files:
                st.error(f"❌ No page JSON files found in {document_folder.name}")
                return
            
            # Create page number mappings
            json_by_page = {}
            md_by_page = {}
            
            # Map JSON files by page number
            for json_file in json_files:
                page_num = extract_page_number(json_file.name)
                if page_num:
                    json_by_page[page_num] = json_file
            
            # Map markdown files by page number
            for md_file in markdown_files:
                page_num = extract_page_number(md_file.name)
                if page_num:
                    md_by_page[page_num] = md_file
            
            # Determine page range
            if total_pdf_pages > 0:
                # Use PDF page count as authoritative
                page_range = range(1, total_pdf_pages + 1)
                st.info(f"🎯 Using PDF page count: pages 1-{total_pdf_pages}")
            else:
                # Fallback: use highest page number found in files
                max_page = max(max(json_by_page.keys(), default=0), max(md_by_page.keys(), default=0))
                page_range = range(1, max_page + 1)
                st.info(f"📊 Using file-based detection: pages 1-{max_page}")
            
            # Track missing and incomplete pages for metadata
            missing_pages = []  # No JSON and no markdown
            incomplete_pages = []  # Has markdown but no JSON (processing failed)
            processed_pages = []
            
            # Process each page in order
            for page_num in page_range:
                if page_num in json_by_page:
                    # Page has JSON data - load it normally
                    try:
                        json_file = json_by_page[page_num]
                        
                        # Load JSON data
                        with open(json_file, 'r') as f:
                            page_data = json.load(f)
                        
                        # Load corresponding markdown if available
                        markdown_content = ""
                        if page_num in md_by_page:
                            try:
                                with open(md_by_page[page_num], 'r') as f:
                                    markdown_content = f.read()
                            except Exception:
                                pass
                        
                        # Create ProcessedTable objects
                        tables = []
                        table_data_list = page_data.get('tables', [])
                        
                        if table_data_list and isinstance(table_data_list, list):
                            for table_data in table_data_list:
                                if isinstance(table_data, dict):
                                    data = table_data.get('data', [])
                                    if data and isinstance(data, list) and len(data) > 0:
                                        table = ProcessedTable(
                                            title=table_data.get('title', 'Untitled Table'),
                                            data=data
                                        )
                                        tables.append(table)
                        
                        # Create ProcessedPage object
                        page = ProcessedPage(
                            title=page_data.get('title', f'Page {page_num}'),
                            content=markdown_content,
                            tables=tables,
                            keywords=page_data.get('keywords', []),
                            pdf_page_number=page_num
                        )
                        processed_pages.append(page)
                        
                    except Exception as e:
                        st.error(f"❌ Error loading page {page_num}: {e}")
                        # Add placeholder for corrupted page
                        processed_pages.append(create_missing_page_placeholder(page_num))
                        missing_pages.append(page_num)
                        
                elif page_num in md_by_page:
                    # Page has markdown but no JSON - processing pipeline failed after stage 1
                    st.warning(f"⚠️ Incomplete processing for page {page_num} - has markdown but no JSON data")
                    try:
                        # Load the parsed markdown content
                        with open(md_by_page[page_num], 'r', encoding='utf-8') as f:
                            markdown_content = f.read()
                        
                        # Create page with markdown content but no tables (since no JSON)
                        page = ProcessedPage(
                            title=f"⚠️ Incomplete - Page {page_num}",
                            content=markdown_content,
                            tables=[],  # No tables since processing failed
                            keywords=["incomplete_processing", "pipeline_failure"],
                            pdf_page_number=page_num
                        )
                        processed_pages.append(page)
                        incomplete_pages.append(page_num)
                        
                    except Exception as e:
                        st.error(f"❌ Error loading markdown for page {page_num}: {e}")
                        # Fallback to placeholder if we can't even read the markdown
                        processed_pages.append(create_missing_page_placeholder(page_num))
                        missing_pages.append(page_num)
                        
                else:
                    # Page has no JSON and no markdown - completely missing
                    st.warning(f"⚠️ Completely missing data for page {page_num}")
                    processed_pages.append(create_missing_page_placeholder(page_num))
                    missing_pages.append(page_num)
            
            if processed_pages:
                # Store missing and incomplete pages info in session state for metadata saving
                st.session_state.missing_pages = missing_pages
                st.session_state.incomplete_pages = incomplete_pages
                
                # Display summary
                if missing_pages:
                    st.warning(f"⚠️ {len(missing_pages)} pages completely missing: {', '.join(map(str, missing_pages))}")
                if incomplete_pages:
                    st.warning(f"⚠️ {len(incomplete_pages)} pages incompletely processed: {', '.join(map(str, incomplete_pages))}")
                
                st.success(f"✅ Loaded {len(processed_pages)} pages with proper PDF alignment")
                self._finalize_document_loading(document_folder, processed_pages)
            else:
                st.error("❌ No pages could be loaded from the document")
                
        except Exception as e:
            st.error(f"❌ Error loading from individual files: {e}")

    def _document_has_been_edited(self, document_folder):
        """Check if document has been edited/reviewed by looking for inspector metadata"""
        metadata_file = document_folder / "inspector_metadata.json"
        
        if not metadata_file.exists():
            return False
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Check for signs of editing/review
            page_statuses = metadata.get('page_statuses', {})
            useless_pages = metadata.get('useless_pages', [])
            flagged_pages = metadata.get('flagged_pages', [])
            portfolio = metadata.get('portfolio')
            
            # If any pages have been approved/reviewed, or marked as useless, or flagged, or portfolio set
            has_page_reviews = any(status in ['approved', 'flagged'] for status in page_statuses.values())
            has_useless_markings = len(useless_pages) > 0
            has_flagged_pages = len(flagged_pages) > 0
            has_portfolio = portfolio is not None and portfolio.strip() != ''
            
            is_edited = has_page_reviews or has_useless_markings or has_flagged_pages or has_portfolio
            
            if is_edited:
                print(f"📝 Document has been edited (reviews: {has_page_reviews}, useless: {has_useless_markings}, flagged: {has_flagged_pages}, portfolio: {has_portfolio})")
            else:
                print(f"📄 Document appears unedited")
                
            return is_edited
            
        except Exception as e:
            print(f"❌ Error reading inspector metadata: {e}")
            return False  # Default to unedited if we can't read metadata

    def _finalize_document_loading(self, document_folder, processed_pages):
        """Finalize document loading - common code for both loading methods"""
        # Update session state
        st.session_state.processed_pages = processed_pages
        st.session_state.document_folder = document_folder
        st.session_state.current_page_idx = 0
        st.session_state.page_statuses = {i: 'pending' for i in range(len(processed_pages))}
        st.session_state.flagged_pages = set()
        st.session_state.edit_mode = False
        
        # Load existing metadata if available
        metadata_path = document_folder / "inspector_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    # Restore portfolio tag
                    st.session_state.portfolio_tag = metadata.get('portfolio', None)
                    # Restore page statuses and flags
                    if 'page_statuses' in metadata:
                        st.session_state.page_statuses.update(metadata['page_statuses'])
                    if 'flagged_pages' in metadata:
                        st.session_state.flagged_pages = set(metadata['flagged_pages'])
                    # Restore missing pages info
                    if 'missing_pages' in metadata:
                        st.session_state.missing_pages = metadata['missing_pages']
                    # Restore incomplete pages info
                    if 'incomplete_pages' in metadata:
                        st.session_state.incomplete_pages = metadata['incomplete_pages']
                    # Restore useless pages info
                    if 'useless_pages' in metadata:
                        st.session_state.useless_pages = metadata['useless_pages']
            except Exception as e:
                st.warning(f"Could not load existing metadata: {e}")
        
        # Count pages with/without tables for informative message
        pages_with_tables = sum(1 for page in processed_pages if page.tables and len(page.tables) > 0)
        pages_without_tables = len(processed_pages) - pages_with_tables
        
        st.success(f"✅ Loaded document: {document_folder.name}")
        st.success(f"📄 {len(processed_pages)} pages ready for review")
        
        if pages_without_tables > 0:
            st.info(f"ℹ️ Note: {pages_without_tables} page(s) contain no tabular data (this is normal)")
        
        st.rerun()

    def render_page_content(self):
        """Render the main page content area"""
        if not st.session_state.processed_pages:
            st.markdown("""
            <div style="text-align: center; padding: 40px; background: #f8f9fa; border-radius: 10px; margin: 20px 0;">
                <h3 style="color: #666;">🥪 Ready to Inspect Documents</h3>
                <p style="color: #888; margin: 10px 0;">Select a processed document from the sidebar to begin quality review</p>
                <p style="font-size: 14px; color: #aaa;">
                    💡 <em>Tip: Place processed documents in the <code>processed_documents/</code> folder</em>
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Random encouraging message
            st.info(f"🎯 {get_random_message('processing')}")
            return
        
        current_page = st.session_state.processed_pages[st.session_state.current_page_idx]
        ui_page_num = st.session_state.current_page_idx + 1  # UI position (1, 2, 3, ...)
        pdf_page_num = current_page.pdf_page_number  # Actual PDF page number
        
        # Check if this is a missing, incomplete, or useless page
        is_missing_page = pdf_page_num in st.session_state.get('missing_pages', [])
        is_incomplete_page = pdf_page_num in st.session_state.get('incomplete_pages', [])
        is_useless_page = pdf_page_num in st.session_state.get('useless_pages', [])
        
        # Note: Removed automatic content-based useless detection to allow users 
        # to type "useless" in content without triggering useless page mode.
        # Pages should only be marked as useless through explicit user action 
        # (clicking "Mark as Useless" button) or when loaded as previously marked useless.
        # is_useless_page already contains the correct value from the useless_pages list.
        
        # Page status indicator
        page_status = st.session_state.page_statuses.get(st.session_state.current_page_idx, 'pending')
        if is_missing_page:
            status_icon = "❌"
        elif is_incomplete_page:
            status_icon = "⚠️"
        elif is_useless_page:
            status_icon = "🗑️"
        else:
            status_icon = "✅" if page_status == 'approved' else "🚩" if st.session_state.current_page_idx in st.session_state.flagged_pages else "⏳"
        
        # Dynamic styling for missing, incomplete, and useless pages
        if is_missing_page:
            header_style = "background: linear-gradient(90deg, #ffe6e6, #fff0f0); border: 2px solid #ff9999;"
            title_color = "#cc0000"
        elif is_incomplete_page:
            header_style = "background: linear-gradient(90deg, #fff3cd, #ffeaa7); border: 2px solid #ffc107;"
            title_color = "#856404"
        elif is_useless_page:
            header_style = "background: linear-gradient(90deg, #f0f0f0, #e8e8e8); border: 2px solid #999999;"
            title_color = "#666666"
        else:
            header_style = "background: linear-gradient(90deg, #f0f2f6, #ffffff); border: 1px solid #e6e9ef;"
            title_color = "#262730"
        
        # Create header with clear page numbering
        if pdf_page_num != ui_page_num:
            page_display = f"PDF Page {pdf_page_num} (UI {ui_page_num}/{len(st.session_state.processed_pages)})"
        else:
            page_display = f"Page {pdf_page_num}/{len(st.session_state.processed_pages)}"
        
        st.markdown(f"""
        <div style="{header_style} padding: 15px; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="margin: 0; color: {title_color};">
                {status_icon} {page_display}: {current_page.title}
            </h3>
            <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">
                <strong>Keywords:</strong> {', '.join(current_page.keywords[:5])}{'...' if len(current_page.keywords) > 5 else ''}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Main comparison layout: PDF on left, extracted data on right
        pdf_col, data_col = st.columns([1.2, 1.8], gap="large")
        
        with pdf_col:
            st.markdown("### 📄 Ground Truth (PDF)")
            
            # Show PDF page info
            st.markdown(f"**📄 PDF Page {pdf_page_num}**")
            
            # Display PDF page
            if st.session_state.document_folder:
                folder_name = st.session_state.document_folder.name
                doc_name = folder_name.split('_')[0]
                pdf_path = st.session_state.document_folder / f"{doc_name}.pdf"
                
                if pdf_path.exists():
                    try:
                        pdf_viewer = PDFViewer(pdf_path)
                        pdf_viewer.render(current_page.pdf_page_number - 1, show_controls=False)
                    except Exception as e:
                        st.error(f"Could not display PDF page {pdf_page_num}: {str(e)}")
                else:
                    st.error(f"PDF not found: {pdf_path}")
        
        with data_col:
            # Special handling for useless pages
            if is_useless_page:
                st.markdown("### 🗑️ Useless Page - No Meaningful Content")
                
                st.markdown("""
                <div style="background: linear-gradient(90deg, #f8f9fa, #e9ecef); padding: 20px; border-radius: 10px; border: 2px dashed #6c757d; text-align: center; margin: 20px 0;">
                    <h3 style="color: #6c757d; margin: 0;">🗑️ USELESS PAGE</h3>
                    <p style="color: #868e96; margin: 10px 0 0 0;">This page contains no meaningful content and was marked as useless during processing.</p>
                    <p style="color: #868e96; margin: 5px 0 0 0; font-size: 14px;"><em>Page maintained for PDF alignment purposes</em></p>
                </div>
                """, unsafe_allow_html=True)
                
                # Show minimal info about why it's useless
                with st.expander("🔍 Debug Info - Why This Page Is Useless", expanded=False):
                    st.write("**Page Title:**", current_page.title)
                    st.write("**Content:**", repr(current_page.content[:100]) if current_page.content else "None")
                    st.write("**Keywords:**", current_page.keywords)
                    st.write("**Tables:**", f"{len(current_page.tables)} table(s)" if current_page.tables else "No tables")
                
                return  # Skip normal content rendering for useless pages
            
            st.markdown("### 🔍 Extracted Data - Verify Accuracy")
            
            # Check what data we have
            has_tables = current_page.tables and len(current_page.tables) > 0
            has_content = current_page.content and current_page.content.strip()
            
            # In edit mode, always show markdown tab even if content is empty
            show_markdown_tab = has_content or st.session_state.edit_mode
            
            # Determine tab structure
            if has_tables and show_markdown_tab:
                tab_labels = ["📊 Tables", "📝 Markdown"]
            elif has_tables:
                tab_labels = ["📊 Tables"]
            elif show_markdown_tab:
                tab_labels = ["📝 Markdown"]
            else:
                tab_labels = ["ℹ️ No Data"]
            
            if len(tab_labels) > 1:
                tabs = st.tabs(tab_labels)
                tab_idx = 0
            else:
                tabs = [st.container()]
                tab_idx = 0
            
            # Tables tab
            if has_tables:
                with tabs[tab_idx]:
                    for i, table in enumerate(current_page.tables):
                        st.markdown(f"#### 📋 {table.title}")
                        
                        if table.data and len(table.data) > 0:
                            if st.session_state.edit_mode:
                                # Edit mode: Show raw JSON for editing
                                st.info("🔧 **EDIT MODE**: Edit the raw JSON data below")
                    
                                # Convert current table data to JSON string
                                table_json = {
                                    "title": table.title,
                                    "data": table.data
                                }
                                json_str = json.dumps(table_json, indent=2, ensure_ascii=False)
                                
                                # Editable JSON text area
                                edited_json_str = st.text_area(
                                    f"Edit table JSON:",
                                    json_str,
                                    height=400,
                                    key=f"json_editor_{st.session_state.current_page_idx}_{i}",
                                    help="Edit the JSON structure. Make sure to keep valid JSON format."
                                )
                            
                                # Try to parse and update if valid JSON
                                try:
                                    if edited_json_str != json_str:
                                        edited_table_data = json.loads(edited_json_str)
                                        if 'data' in edited_table_data:
                                            # Update the actual session state objects, not local variables
                                            st.session_state.processed_pages[st.session_state.current_page_idx].tables[i].data = edited_table_data['data']
                                            if 'title' in edited_table_data:
                                                st.session_state.processed_pages[st.session_state.current_page_idx].tables[i].title = edited_table_data['title']
                                            st.success("✅ JSON updated in memory! Click 'Stop Editing' or 'Save Changes' to persist.")
                                            # Note: We don't auto-save to disk here anymore to avoid constant I/O
                                            # Changes are saved in session state and will persist when user explicitly saves
                                except json.JSONDecodeError as e:
                                    st.error(f"❌ Invalid JSON: {str(e)}")
                                except Exception as e:
                                    st.error(f"❌ Error updating table: {str(e)}")
                            else:
                                # View mode: Show table normally
                                try:
                                    # Handle different data formats
                                    if not table.data:
                                        st.warning("⚠️ Table data is empty")
                                        continue
                                    
                                    # Check if data is properly formatted
                                    if isinstance(table.data[0], dict):
                                        # Standard format: list of dictionaries
                                        df = pd.DataFrame(table.data)
                                    elif isinstance(table.data[0], list):
                                        # Alternative format: list of lists (needs column names)
                                        st.warning("⚠️ Table data is in list format, converting to DataFrame")
                                        # Use generic column names
                                        max_cols = max(len(row) for row in table.data) if table.data else 0
                                        column_names = [f"Column_{i+1}" for i in range(max_cols)]
                                        df = pd.DataFrame(table.data, columns=column_names)
                                    else:
                                        # Unknown format
                                        st.error(f"❌ Unsupported table data format: {type(table.data[0])}")
                                        st.write("**Raw data:**", table.data[:3])  # Show first 3 items for debugging
                                        continue
                                    
                                    # Convert complex data types to strings for Arrow compatibility
                                    for col in df.columns:
                                        if df[col].dtype == 'object':
                                            # Convert any dict, list, or complex objects to strings
                                            df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (dict, list)) else x)
                                            # Handle any remaining non-string objects
                                            df[col] = df[col].astype(str)
                                    
                                except Exception as e:
                                    st.error(f"❌ Error processing table data: {str(e)}")
                                    st.write("**Raw table data structure:**")
                                    st.write(f"- Data type: {type(table.data)}")
                                    st.write(f"- Data length: {len(table.data) if table.data else 0}")
                                    if table.data:
                                        st.write(f"- First item type: {type(table.data[0])}")
                                        st.write(f"- First item: {table.data[0]}")
                                    continue
                                
                                st.markdown(f"*{len(df)} rows × {len(df.columns)} columns*")
                                
                                # Read-only table with better formatting
                                st.dataframe(
                                    df, 
                                    use_container_width=True,
                                    height=min(400, len(df) * 35 + 100)
                                )
                        else:
                            st.warning("⚠️ No table data found")
                        
                        if i < len(current_page.tables) - 1:
                            st.markdown("---")
                
                tab_idx += 1
            
            # Markdown tab (if there are tables) or main content
            if show_markdown_tab:
                markdown_container = tabs[tab_idx] if len(tab_labels) > 1 else tabs[0]
                
                with markdown_container:
                    if st.session_state.edit_mode:
                        st.info("🔧 **EDIT MODE**: Review and correct the markdown content")
                        edited_content = st.text_area(
                            "Markdown content:",
                            current_page.content or "",  # Use empty string if content is None
                            height=500,
                            key=f"markdown_editor_{st.session_state.current_page_idx}",
                            help="Edit the markdown to match the PDF content exactly"
                        )
                        # Update content if changed
                        if edited_content != (current_page.content or ""):
                            # Update the actual session state object, not local variable
                            st.session_state.processed_pages[st.session_state.current_page_idx].content = edited_content
                            st.info("📝 Markdown updated in memory! Click 'Stop Editing' or 'Save Changes' to persist.")
                    else:
                        if has_content:
                            st.markdown("**📝 Extracted Content:**")
                            # Fixed height scrollable container for markdown
                            st.text_area(
                                "Markdown content (read-only):",
                                current_page.content,
                                height=500,
                                disabled=True,
                                label_visibility="collapsed",
                                help="Scroll to view full content. Switch to Edit Mode to make changes."
                            )
                        else:
                            st.info("📝 **No markdown content found**")
                            st.markdown("This page has no extracted markdown content. Switch to Edit Mode to add content manually.")
            
            # Handle special cases for incomplete and empty pages
            if is_incomplete_page:
                # Show special message for incomplete processing
                st.error("⚠️ **Incomplete Processing Detected**")
                st.markdown("""
                **This page was only partially processed by the pipeline:**
                
                ✅ **Stage 1 (Peanut/Parse):** PDF → Markdown ✅ *Successful*  
                ❌ **Stage 2 (Butter/Better):** Markdown Enhancement ❌ *Failed*  
                ❌ **Stage 3 (Jelly/JSON):** Data Extraction ❌ *Skipped*  
                
                **What you're seeing:**
                - ✅ Raw parsed markdown content from Stage 1
                - ❌ No enhanced formatting or structure  
                - ❌ No extracted table data or JSON
                
                **Possible causes:**
                - Processing pipeline error in Stage 2
                - Complex page layout that couldn't be enhanced
                - Memory or timeout issues during processing
                
                **Next steps:**
                - 🔄 Reprocess this page individually through the full pipeline
                - 🔍 Check pipeline logs for specific error messages
                - 🚩 Flag this page for manual review if reprocessing fails
                """)
            elif not has_tables and not has_content and not st.session_state.edit_mode:
                with tabs[0]:
                    st.info("📄 **No tabular data found on this page**")
                    st.markdown("""
                    This page appears to contain only text content or images without structured tables.
                    
                    *This is normal for many PDF pages - not all pages contain tabular data that can be extracted.*
                    """)
                    
                    # Still show approval buttons for pages with no data
                    st.markdown("You can still approve this page if the PDF content doesn't require data extraction.")
        
        # Action buttons - prominent and clear
        st.markdown("---")
        st.markdown("### 🎯 Review Actions")
        
        button_col1, button_col2, button_col3, button_col4, button_col5 = st.columns([1, 1, 1, 1, 1])
        
        with button_col1:
            edit_button_text = "🔧 Stop Editing" if st.session_state.edit_mode else "✏️ Edit Mode"
            if st.button(edit_button_text, use_container_width=True, type="secondary"):
                # If stopping edit mode, save any pending changes first
                if st.session_state.edit_mode:
                    try:
                        self.save_current_state()
                        st.success("💾 Edits saved!")
                    except Exception as e:
                        st.error(f"❌ Error saving edits: {str(e)}")
                
                st.session_state.edit_mode = not st.session_state.edit_mode
                st.rerun()
        
        with button_col2:
            if st.button("✅ Approve Page", use_container_width=True, type="primary"):
                st.session_state.page_statuses[st.session_state.current_page_idx] = 'approved'
                if st.session_state.current_page_idx in st.session_state.flagged_pages:
                    st.session_state.flagged_pages.remove(st.session_state.current_page_idx)
                self.save_current_state()
                st.success("✅ Page approved!")
                st.balloons()
        
        with button_col3:
            if st.button("🗑️ Mark as Useless", use_container_width=True):
                if self.mark_page_as_useless(st.session_state.current_page_idx):
                    current_page = st.session_state.processed_pages[st.session_state.current_page_idx]
                    st.success(f"🗑️ Page {current_page.pdf_page_number} marked as useless!")
                    st.info("📄 All content replaced with 'useless' and saved to disk")
                    st.rerun()
        
        with button_col4:
            if st.button("💾 Save Changes", use_container_width=True):
                try:
                    self.save_current_state()
                    # Show detailed feedback about what was saved
                    final_output_file = st.session_state.document_folder / "final_output.json"
                    if final_output_file.exists():
                        st.success("💾 Changes saved to final_output.json!")
                    else:
                        st.success("💾 Changes saved to individual JSON files!")
                    current_page = st.session_state.processed_pages[st.session_state.current_page_idx]
                    st.info(f"📄 Saved PDF page {current_page.pdf_page_number} data to disk")
                except Exception as e:
                    st.error(f"❌ Error saving changes: {str(e)}")
                    st.error("Check file permissions and try again")
        
        with button_col5:
            if st.button("🏁 Export Final", use_container_width=True):
                self.create_final_output_folder()
        
        # Status indicator
        if st.session_state.edit_mode:
            st.info("🔧 **EDIT MODE ACTIVE** - Make your corrections above. Changes save to memory automatically and persist to disk when you click 'Stop Editing' or 'Save Changes'.")
        
        # Debug info (only show if there are page ordering issues)
        if st.button("🔍 Debug Page Order", help="Show detailed page ordering information"):
            self._show_debug_info()
        
        # Quick navigation
        if len(st.session_state.processed_pages) > 1:
            st.markdown("### ⏭️ Quick Navigation")
            nav_cols = st.columns(min(len(st.session_state.processed_pages), 10))
            
            for i in range(len(st.session_state.processed_pages)):
                if i < 10:  # Limit to 10 buttons
                    col_idx = i % len(nav_cols)
                    with nav_cols[col_idx]:
                        status = st.session_state.page_statuses.get(i, 'pending')
                        is_flagged = i in st.session_state.flagged_pages
                        page = st.session_state.processed_pages[i]
                        is_missing = page.pdf_page_number in st.session_state.get('missing_pages', [])
                        is_incomplete = page.pdf_page_number in st.session_state.get('incomplete_pages', [])
                        is_useless = page.pdf_page_number in st.session_state.get('useless_pages', [])
                        
                        if is_missing:
                            icon = "❌"
                        elif is_incomplete:
                            icon = "⚠️"
                        elif is_useless:
                            icon = "🗑️"
                        elif status == 'approved':
                            icon = "✅"
                        elif is_flagged:
                            icon = "🚩"
                        else:
                            icon = "⏳"
                            
                        is_current = i == st.session_state.current_page_idx
                        
                        if st.button(
                            f"{icon} {i+1}", 
                            key=f"nav_{i}",
                            disabled=is_current,
                            use_container_width=True
                        ):
                            st.session_state.current_page_idx = i
                            st.rerun()

    def save_current_state(self):
        """Save current state back to appropriate format (final_output.json or individual files)"""
        if not st.session_state.document_folder or not st.session_state.processed_pages:
            st.warning("⚠️ No document loaded or no data to save")
            return
        
        try:
            # Check which format we're working with
            final_output_file = st.session_state.document_folder / "final_output.json"
            
            if final_output_file.exists():
                # Save back to final_output.json format
                self._save_to_final_output(final_output_file)
                print(f"✅ Saved to final_output.json: {final_output_file}")
            else:
                # Save back to individual files format
                self._save_to_individual_files()
                print(f"✅ Saved to individual files in: {st.session_state.document_folder}")
            
            # Always save inspector metadata
            self._save_inspector_metadata()
            print(f"✅ Saved inspector metadata")
                
        except Exception as e:
            print(f"❌ Error saving state: {str(e)}")
            st.error(f"Error saving state: {str(e)}")
            raise  # Re-raise to let the caller handle it

    def _save_to_final_output(self, final_output_file):
        """Save changes back to final_output.json format"""
        import tempfile
        import shutil
        
        try:
            # Load existing final_output.json
            with open(final_output_file, 'r') as f:
                final_data = json.load(f)
            
            # Update the pages data with our changes
            if 'pages' in final_data:
                for i, page in enumerate(st.session_state.processed_pages):
                    if i < len(final_data['pages']):
                        # Update the page data
                        page_data = final_data['pages'][i]
                        
                        # Update title if changed
                        page_data['title'] = page.title
                        
                        # Update keywords if changed
                        page_data['keywords'] = page.keywords
                        
                        # Update content - save to both raw_content and content fields for compatibility
                        if page.content:
                            page_data['raw_content'] = page.content
                            page_data['content'] = page.content
                        
                        # Update tables - convert back to rows format
                        if page.tables:
                            # Update existing tables or create new ones
                            updated_tables = []
                            for j, table in enumerate(page.tables):
                                if j < len(page_data.get('tables', [])):
                                    # Update existing table
                                    table_data = page_data['tables'][j]
                                    table_data['title'] = table.title
                                    table_data['rows'] = table.data  # Our data format is already rows format
                                    
                                    # Update metadata if it exists
                                    if 'metadata' in table_data and table.data:
                                        table_data['metadata']['row_count'] = len(table.data)
                                        if table.data:
                                            table_data['metadata']['column_count'] = len(table.data[0]) if table.data[0] else 0
                                    
                                    updated_tables.append(table_data)
                                else:
                                    # Create new table
                                    new_table = {
                                        'table_id': f'table_{j+1}',
                                        'title': table.title,
                                        'description': '',
                                        'rows': table.data,
                                        'metadata': {
                                            'row_count': len(table.data) if table.data else 0,
                                            'column_count': len(table.data[0]) if table.data and table.data[0] else 0,
                                            'data_types': []
                                        }
                                    }
                                    updated_tables.append(new_table)
                            
                            page_data['tables'] = updated_tables
                        else:
                            # No tables - set empty array
                            page_data['tables'] = []
            
            # Use atomic write to prevent corruption during disk full situations
            # Write to temporary file first, then move to final location
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode='w', 
                    encoding='utf-8', 
                    suffix='.json',
                    dir=final_output_file.parent,
                    delete=False
                ) as temp_file:
                    json.dump(final_data, temp_file, indent=2, ensure_ascii=False)
                    temp_file_path = temp_file.name
                
                # Atomically move the temp file to replace the original
                shutil.move(temp_file_path, final_output_file)
                
                print(f"✅ Successfully wrote {len(final_data.get('pages', []))} pages to {final_output_file}")
                
            except Exception as atomic_error:
                # Clean up temp file if it exists
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                raise atomic_error
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error saving to final_output.json: {error_msg}")
            
            # Provide helpful suggestions based on error type
            if "No space left on device" in error_msg:
                st.error("💾 **Disk Full Error**: Please free up disk space and try again. The file was not corrupted.")
            elif "Expecting value" in error_msg or "Unterminated" in error_msg:
                st.error("🔧 **Corrupted JSON detected**: Please run `python fix_corrupted_json.py` to repair the file.")
            else:
                st.error(f"Error saving to final_output.json: {error_msg}")
            raise

    def _save_to_individual_files(self):
        """Save changes back to individual file format (backward compatibility)"""
        try:
            # Save back to the individual page JSON files in 03_cleaned_json
            json_folder = st.session_state.document_folder / "03_cleaned_json"
            
            for page in st.session_state.processed_pages:
                # Skip saving placeholders for missing pages (they don't have real data)
                if page.title.startswith("❌ Missing Data"):
                    continue
                    
                # Convert to the original JSON format
                page_data = {
                    "title": page.title,
                    "keywords": page.keywords,
                    "tables": []
                }
                
                # Add table data - handle empty tables gracefully
                if page.tables and len(page.tables) > 0:
                    for table in page.tables:
                        table_data = {
                            "title": table.title,
                            "data": table.data
                        }
                        page_data["tables"].append(table_data)
                # If page.tables is empty, tables list remains empty in JSON
            
                # Save individual page JSON using PDF page number, not UI index
                page_file = json_folder / f"page_{page.pdf_page_number}.json"
                with open(page_file, 'w', encoding='utf-8') as f:
                    json.dump(page_data, f, indent=2, ensure_ascii=False)
            
            # Count non-placeholder pages for logging
            real_pages = [p for p in st.session_state.processed_pages if not p.title.startswith("❌ Missing Data")]
            print(f"✅ Successfully wrote {len(real_pages)} JSON files to {json_folder}")
            
            # Also save back to PARSED markdown files (01_parsed_markdown, NOT 02_enhanced_markdown)
            # We use the original parsed markdown to maintain data integrity
            markdown_folder = st.session_state.document_folder / "01_parsed_markdown"
            if markdown_folder.exists():
                for page in st.session_state.processed_pages:
                    # Skip saving placeholders for missing pages
                    if page.title.startswith("❌ Missing Data"):
                        continue
                        
                    # Save markdown using PDF page number, not UI index
                    markdown_file = markdown_folder / f"page_{page.pdf_page_number}.md"
                    with open(markdown_file, 'w', encoding='utf-8') as f:
                        # Handle empty content gracefully
                        content_to_save = page.content if page.content else ""
                        f.write(content_to_save)
                
                print(f"✅ Successfully wrote {len(real_pages)} markdown files to {markdown_folder}")
            else:
                print(f"⚠️ Markdown folder {markdown_folder} does not exist, skipping markdown save")
                    
        except Exception as e:
            print(f"❌ Error saving to individual files: {str(e)}")
            st.error(f"Error saving to individual files: {str(e)}")
            raise

    def _save_inspector_metadata(self):
        """Save inspector metadata (common for both formats)"""
        try:
            # Save inspector metadata (including portfolio tag and missing/incomplete pages)
            inspector_metadata = {
                'page_statuses': st.session_state.page_statuses,
                'flagged_pages': list(st.session_state.flagged_pages),
                'missing_pages': st.session_state.get('missing_pages', []),
                'incomplete_pages': st.session_state.get('incomplete_pages', []),
                'useless_pages': st.session_state.get('useless_pages', []),
                'last_updated': datetime.now().isoformat(),
                'total_pages': len(st.session_state.processed_pages),
                'portfolio': st.session_state.get('portfolio_tag', None)
            }
            
            metadata_path = st.session_state.document_folder / "inspector_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(inspector_metadata, f, indent=2)
                
        except Exception as e:
            st.error(f"Error saving inspector metadata: {str(e)}")

    def save_portfolio_tag(self):
        """Save portfolio tag to metadata immediately"""
        if not st.session_state.document_folder:
            return
        
        try:
            metadata_path = st.session_state.document_folder / "inspector_metadata.json"
            
            # Load existing metadata or create new
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    inspector_metadata = json.load(f)
            else:
                inspector_metadata = {}
            
            # Update portfolio tag
            inspector_metadata['portfolio'] = st.session_state.get('portfolio_tag', None)
            inspector_metadata['last_updated'] = datetime.now().isoformat()
            
            # Save back
            with open(metadata_path, 'w') as f:
                json.dump(inspector_metadata, f, indent=2)
                
        except Exception as e:
            st.error(f"Error saving portfolio tag: {str(e)}")

    def create_final_output_folder(self):
        """Create final output folder with consolidated markdown and JSON"""
        if not st.session_state.document_folder or not st.session_state.processed_pages:
            st.error("No processed data to export")
            return
        
        try:
            # Get document name (e.g., "short" from "short_20250624_142041" or from document_id)
            source_folder_name = st.session_state.document_folder.name
            
            # Try to get document name from various sources
            doc_name = source_folder_name.split('_')[0]
            
            # If we have a final_output.json, try to get document name from there
            final_output_file = st.session_state.document_folder / "final_output.json"
            if final_output_file.exists():
                try:
                    with open(final_output_file, 'r') as f:
                        final_data = json.load(f)
                    # Try to extract document name from document_info
                    if 'document_info' in final_data:
                        doc_info = final_data['document_info']
                        if 'document_id' in doc_info:
                            # Extract from document_id like "doc_20250625_211701"
                            doc_id_parts = doc_info['document_id'].split('_')
                            if len(doc_id_parts) > 0 and doc_id_parts[0] == 'doc':
                                # Use the timestamp part or just use 'doc'
                                doc_name = 'doc'
                except Exception:
                    pass  # Fall back to folder name approach
            
            # Create final output directory with format: final_pdfname_timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            final_output_dir = Path(f"final_{doc_name}_{timestamp}")
            final_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. Copy original PDF and metadata files
            pdf_candidates = [
                st.session_state.document_folder / f"{doc_name}.pdf",
                st.session_state.document_folder / "document.pdf"
            ]
            
            # Find the PDF file
            pdf_found = False
            for pdf_path in pdf_candidates:
                if pdf_path.exists():
                    import shutil
                    shutil.copy2(pdf_path, final_output_dir / f"{doc_name}.pdf")
                    pdf_found = True
                    break
            
            # Copy metadata files if they exist
            metadata_files_to_copy = [
                ("document_metadata.json", "document_metadata.json"),
                ("pipeline_summary.json", "pipeline_summary.json"),
                ("inspector_metadata.json", "inspector_metadata.json"),
                ("final_output.json", "original_final_output.json")  # Keep original for reference
            ]
            
            import shutil
            for src_name, dst_name in metadata_files_to_copy:
                src_path = st.session_state.document_folder / src_name
                if src_path.exists():
                    shutil.copy2(src_path, final_output_dir / dst_name)
            
            # 2. Create consolidated final JSON in the new format
            consolidated_json = {
                "document_info": {
                    "document_name": doc_name,
                    "export_date": datetime.now().isoformat(),
                    "total_pages": len(st.session_state.processed_pages),
                    "total_tables": sum(len(page.tables) for page in st.session_state.processed_pages),
                    "portfolio": st.session_state.get('portfolio_tag', None),
                    "review_status": {
                        "approved_pages": len([i for i in st.session_state.page_statuses.values() if i == 'approved']),
                        "flagged_pages": len(st.session_state.flagged_pages),
                        "missing_pages": st.session_state.get('missing_pages', []),
                        "incomplete_pages": st.session_state.get('incomplete_pages', []),
                        "useless_pages": st.session_state.get('useless_pages', [])
                    }
                },
                "pages": []
            }
            
            # Add all page data in the new format
            for i, page in enumerate(st.session_state.processed_pages):
                page_data = {
                    "page_id": f"page_{i+1}",
                    "title": page.title,
                    "summary": f"Page {i+1} content",
                    "keywords": page.keywords,
                    "tables": [],
                    "raw_content": page.content,
                    "processing_metadata": {
                        "review_status": st.session_state.page_statuses.get(i, 'pending'),
                        "flagged": i in st.session_state.flagged_pages,
                        "last_reviewed": datetime.now().isoformat()
                    }
                }
                
                # Add table data in the new "rows" format
                for j, table in enumerate(page.tables):
                    table_data = {
                        "table_id": f"table_{j+1}",
                        "title": table.title,
                        "description": f"Table from page {i+1}",
                        "rows": table.data,  # Already in correct format
                        "metadata": {
                            "row_count": len(table.data) if table.data else 0,
                            "column_count": len(table.data[0]) if table.data and table.data[0] else 0,
                            "data_types": []
                        }
                    }
                    page_data["tables"].append(table_data)
                
                consolidated_json["pages"].append(page_data)
            
            # Save consolidated JSON
            final_json_path = final_output_dir / f"{doc_name}_final.json"
            with open(final_json_path, 'w') as f:
                json.dump(consolidated_json, f, indent=2, ensure_ascii=False)
            
            # 3. Create consolidated markdown
            consolidated_markdown = f"# {doc_name} - Final Document\n\n"
            consolidated_markdown += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Add all page content
            for i, page in enumerate(st.session_state.processed_pages):
                consolidated_markdown += f"## Page {i+1}: {page.title}\n\n"
                
                # Add keywords
                if page.keywords:
                    consolidated_markdown += f"**Keywords:** {', '.join(page.keywords)}\n\n"
                
                # Add content
                if page.content:
                    consolidated_markdown += page.content + "\n\n"
                
                # Add table summaries
                if page.tables:
                    consolidated_markdown += f"**Tables on this page:** {len(page.tables)}\n"
                    for j, table in enumerate(page.tables):
                        consolidated_markdown += f"- {table.title} ({len(table.data)} rows)\n"
                    consolidated_markdown += "\n"
                
                consolidated_markdown += "---\n\n"
            
            # Save consolidated markdown
            final_md_path = final_output_dir / f"{doc_name}_final.md"
            with open(final_md_path, 'w', encoding='utf-8') as f:
                f.write(consolidated_markdown)
            
            portfolio_info = f"\n            - 🏷️ Portfolio: {st.session_state.portfolio_tag}" if st.session_state.get('portfolio_tag') else ""
            pdf_info = "- 📄 Original PDF" if pdf_found else "- ⚠️ Original PDF not found"
            missing_pages = st.session_state.get('missing_pages', [])
            missing_info = f"\n            - ❌ Missing Data: {len(missing_pages)} pages ({', '.join(map(str, missing_pages))})" if missing_pages else ""
            incomplete_pages = st.session_state.get('incomplete_pages', [])
            incomplete_info = f"\n            - ⚠️ Incomplete Processing: {len(incomplete_pages)} pages ({', '.join(map(str, incomplete_pages))})" if incomplete_pages else ""
            useless_pages = st.session_state.get('useless_pages', [])
            useless_info = f"\n            - 🗑️ Useless Pages: {len(useless_pages)} pages ({', '.join(map(str, useless_pages))})" if useless_pages else ""
            
            st.success(f"""
            🎉 **Final Output Created Successfully!**
            
            **Location:** `{final_output_dir}`
            
            **Files Created:**
            - {pdf_info}
            - 📊 `{doc_name}_final.json` - Consolidated JSON data (new format)
            - 📝 `{doc_name}_final.md` - Consolidated markdown
            - 📋 Metadata files (document, pipeline, inspector)
            
            **Review Status:**
            - ✅ Approved: {len([i for i in st.session_state.page_statuses.values() if i == 'approved'])} pages
            - 🚩 Flagged: {len(st.session_state.flagged_pages)} pages  
            - 📊 Total Tables: {sum(len(page.tables) for page in st.session_state.processed_pages)}{portfolio_info}{missing_info}{incomplete_info}{useless_info}
            """)
            
        except Exception as e:
            st.error(f"❌ Error creating final output folder: {str(e)}")

    def _show_debug_info(self):
        """Show debugging information about page ordering"""
        st.markdown("### 🔍 Debug Information")
        
        if not st.session_state.processed_pages:
            st.warning("No pages loaded")
            return
        
        # Create debug table
        debug_data = []
        for i, page in enumerate(st.session_state.processed_pages):
            debug_data.append({
                "UI Index": i,
                "UI Position": i + 1,
                "PDF Page #": page.pdf_page_number,
                "Title": page.title[:50] + "..." if len(page.title) > 50 else page.title,
                "Has Tables": len(page.tables) > 0,
                "Has Content": bool(page.content and page.content.strip()),
                "Is Missing": page.title.startswith("❌ Missing Data"),
                "Is Incomplete": page.title.startswith("⚠️ Incomplete")
            })
        
        debug_df = pd.DataFrame(debug_data)
        st.dataframe(debug_df, use_container_width=True)
        
        # Show order issues
        expected_order = list(range(1, len(st.session_state.processed_pages) + 1))
        actual_order = [page.pdf_page_number for page in st.session_state.processed_pages]
        
        if expected_order != actual_order:
            st.error("🚨 **Page Order Issue Detected!**")
            st.markdown(f"**Expected:** {expected_order}")
            st.markdown(f"**Actual:** {actual_order}")
            
            # Show gaps
            gaps = []
            for i in range(1, max(actual_order) + 1):
                if i not in actual_order:
                    gaps.append(i)
            if gaps:
                st.warning(f"**Missing page numbers:** {gaps}")
                
            # Show duplicates
            duplicates = []
            seen = set()
            for page_num in actual_order:
                if page_num in seen:
                    duplicates.append(page_num)
                seen.add(page_num)
            if duplicates:
                st.error(f"**Duplicate page numbers:** {duplicates}")
        else:
            st.success("✅ Page order is correct!")
        
        # Show session state info
        st.markdown("**Session State Info:**")
        st.markdown(f"- Total pages: {len(st.session_state.processed_pages)}")
        st.markdown(f"- Current page: {st.session_state.current_page_idx}")
        st.markdown(f"- Missing pages: {st.session_state.get('missing_pages', [])}")
        st.markdown(f"- Incomplete pages: {st.session_state.get('incomplete_pages', [])}")
        st.markdown(f"- Useless pages: {st.session_state.get('useless_pages', [])}")

    def mark_page_as_useless(self, page_index):
        """Mark a page as useless by replacing its content with 'useless'"""
        try:
            # Get the page reference directly from session state to ensure persistence
            current_page = st.session_state.processed_pages[page_index]
            page_number = current_page.pdf_page_number
            
            print(f"🗑️ Marking page {page_index + 1} (PDF page {page_number}) as useless")
            
            # Replace all table data with "useless" - update session state directly
            for i, table in enumerate(current_page.tables):
                st.session_state.processed_pages[page_index].tables[i].title = "useless"
                st.session_state.processed_pages[page_index].tables[i].data = [{"content": "useless"}]
            
            # Replace markdown content and title with "useless" - update session state directly
            st.session_state.processed_pages[page_index].content = "useless"
            st.session_state.processed_pages[page_index].title = f"Useless - Page {page_number}"
            
            # Update keywords to reflect useless status
            st.session_state.processed_pages[page_index].keywords = ["useless"]
            
            # Add to useless pages tracking (track by PDF page number)
            if page_number not in st.session_state.useless_pages:
                st.session_state.useless_pages.append(page_number)
                st.session_state.useless_pages.sort()  # Keep sorted for display
            
            # Remove from other statuses to avoid conflicts
            if page_index in st.session_state.page_statuses:
                del st.session_state.page_statuses[page_index]
            if page_index in st.session_state.flagged_pages:
                st.session_state.flagged_pages.remove(page_index)
            
            print(f"✅ Page {page_index + 1} marked as useless, saving changes...")
            
            # Auto-save the changes to disk
            self.save_current_state()
            
            print(f"✅ Changes saved for useless page {page_index + 1}")
            
            return True
        except Exception as e:
            print(f"❌ Error marking page as useless: {e}")
            st.error(f"Error marking page as useless: {e}")
            return False

    def run(self):
        """Main app runner"""
        self.render_header()
        self.render_sidebar()
        self.render_page_content()

# Main execution
if __name__ == "__main__":
    inspector = SandwichInspector()
    inspector.run() 