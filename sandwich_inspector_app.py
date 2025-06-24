#!/usr/bin/env python3
"""
🥪 Sandwich Inspector App
========================

A Streamlit app for inspecting and correcting PDF processing pipeline outputs.
Integrates with the PB&J pipeline for quality control and manual correction.
"""

import streamlit as st
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
import os

# Add PB&J pipeline to path
sys.path.insert(0, str(Path("peanut_butter_jelly/src")))

from pbj.sandwich import Sandwich
from pbj.config import create_config
from pbj.jelly import ProcessedPage, ProcessedTable
from pdf_utils import PDFViewer
from inspector_config import get_random_message

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
        if 'processing' not in st.session_state:
            st.session_state.processing = False
        
        # FIXED: Add processing recovery mechanism
        if 'processing_start_time' not in st.session_state:
            st.session_state.processing_start_time = None
            
        # Check for stuck processing state (timeout after 5 minutes)
        if st.session_state.processing and st.session_state.processing_start_time:
            from datetime import datetime
            if datetime.now().timestamp() - st.session_state.processing_start_time > 300:  # 5 minutes
                st.session_state.processing = False
                st.session_state.processing_start_time = None
                st.warning("⚠️ Processing timeout detected - resetting state")

    def render_header(self):
        """Render the main header"""
        st.markdown("""
        <div class="main-header">
            <h1>🥪 Sandwich Inspector</h1>
            <p>Quality control for your PDF processing pipeline</p>
        </div>
        """, unsafe_allow_html=True)

    def render_sidebar(self):
        """Render the sidebar with navigation and controls"""
        st.sidebar.markdown("## 🥪 Fresh Ingredients")
        
        # Get available PDFs from data directory
        data_dir = Path("data")
        if data_dir.exists():
            pdf_files = list(data_dir.glob("*.pdf"))
            if pdf_files:
                pdf_names = [pdf.name for pdf in pdf_files]
                
                selected_pdf = st.sidebar.selectbox(
                    "Select PDF to work with:",
                    pdf_names,
                    help="Choose a PDF from the data directory"
                )
                
                if selected_pdf:
                    selected_pdf_path = data_dir / selected_pdf
                    
                    # Check if this PDF has been processed before
                    existing_results = self.find_existing_results(selected_pdf)
                    
                    st.sidebar.markdown("### 🎛️ Action Options")
                    
                    col1, col2 = st.sidebar.columns(2)
                    
                    with col1:
                        if st.button("🔥 Process", disabled=st.session_state.processing):
                            if not st.session_state.processing:
                                st.session_state.processing = True
                                st.session_state.processing_start_time = datetime.now().timestamp()
                                self.process_pdf_from_data(selected_pdf_path)
                    
                    with col2:
                        if existing_results and st.button("📖 Open Results"):
                            self.load_existing_results(existing_results[0])  # Load most recent
                    
                    if st.session_state.processing:
                        st.sidebar.info("🔥 Cooking in progress... Please wait!")
                    
                    # Show existing results info
                    if existing_results:
                        st.sidebar.markdown("### 📚 Existing Results")
                        for i, result_folder in enumerate(existing_results[:3]):  # Show last 3
                            result_name = result_folder.name
                            timestamp = result_name.split('_')[-2:]  # Get date and time
                            if len(timestamp) == 2:
                                date_str = f"{timestamp[0][:4]}-{timestamp[0][4:6]}-{timestamp[0][6:8]}"
                                time_str = f"{timestamp[1][:2]}:{timestamp[1][2:4]}:{timestamp[1][4:6]}"
                                display_name = f"{date_str} {time_str}"
                            else:
                                display_name = result_name
                            
                            if st.sidebar.button(f"📄 {display_name}", key=f"load_{i}"):
                                self.load_existing_results(result_folder)
            else:
                st.sidebar.warning("No PDF files found in data/ directory")
        else:
            st.sidebar.error("data/ directory not found")
        
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
            
            # Direct page selection
            new_page = st.sidebar.selectbox(
                "Jump to page:",
                range(1, total_pages + 1),
                index=current_page - 1
            ) - 1
            
            if new_page != st.session_state.current_page_idx:
                st.session_state.current_page_idx = new_page
                st.rerun()
                
            st.sidebar.markdown("---")
            
            # Quality control summary
            st.sidebar.markdown("## 📊 Quality Summary")
            approved = sum(1 for status in st.session_state.page_statuses.values() if status == 'approved')
            flagged = len(st.session_state.flagged_pages)
            pending = total_pages - approved - flagged
            
            st.sidebar.markdown(f"""
            <div class="quality-badge approved">✅ Approved: {approved}</div><br>
            <div class="quality-badge flagged">🚩 Flagged: {flagged}</div><br>
            <div class="quality-badge pending">⏳ Pending: {pending}</div>
            """, unsafe_allow_html=True)
            
            # Flagged items review
            if st.session_state.flagged_pages:
                st.sidebar.markdown("## 🚩 Items to Review")
                for page_idx in sorted(st.session_state.flagged_pages):
                    page_title = st.session_state.processed_pages[page_idx].title
                    if st.sidebar.button(f"📄 Page {page_idx + 1}: {page_title[:20]}..."):
                        st.session_state.current_page_idx = page_idx
                        st.rerun()
            
            st.sidebar.markdown("---")
            
            # Final export section
            st.sidebar.markdown("## 🏁 Final Export")
            
            # Show completion progress
            completion_pct = ((approved + flagged) / total_pages * 100) if total_pages > 0 else 0
            st.sidebar.progress(completion_pct / 100)
            st.sidebar.markdown(f"**Review Progress:** {completion_pct:.1f}%")
            
            if st.sidebar.button("🏁 Create Final Output Folder", 
                               use_container_width=True,
                               help="Create a clean final output folder with all your reviewed content"):
                self.create_final_output_folder()
            
            st.sidebar.markdown("*Creates a clean folder with your final JSON, markdown summary, and original PDF*")

    def find_existing_results(self, pdf_name):
        """Find existing processed results for a PDF"""
        processed_dir = Path("peanut_butter_jelly/processed_documents")
        if not processed_dir.exists():
            return []
        
        # Look for folders that start with the PDF name (without extension)
        pdf_base = pdf_name.replace('.pdf', '')
        matching_folders = []
        
        for folder in processed_dir.iterdir():
            if folder.is_dir() and folder.name.startswith(pdf_base):
                # Check if it has final_output.json
                if (folder / "final_output.json").exists():
                    matching_folders.append(folder)
        
        # Sort by modification time (newest first)
        matching_folders.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return matching_folders

    def load_existing_results(self, result_folder):
        """Load existing processed results"""
        try:
            final_output_path = result_folder / "final_output.json"
            if final_output_path.exists():
                with open(final_output_path, 'r') as f:
                    data = json.load(f)
                
                # FIXED: Handle both old (list) and new (dict with pages key) JSON formats
                if isinstance(data, list):
                    # Old format: direct list of pages
                    pages_data = data
                    st.info("📄 Loading legacy format - will upgrade to new format on save")
                elif isinstance(data, dict) and 'pages' in data:
                    # New format: structured with document_info and pages
                    pages_data = data['pages']
                elif isinstance(data, dict):
                    # Fallback: treat entire dict as single page (shouldn't happen but safe)
                    pages_data = [data] if data else []
                    st.warning("⚠️ Unusual JSON format detected - attempting to load")
                else:
                    # Unknown format
                    st.error("❌ Unrecognized JSON format")
                    return
                
                # Convert to ProcessedPage objects
                processed_pages = []
                for page_data in pages_data:
                    try:
                        tables = []
                        for table_data in page_data.get('tables', []):
                            table = ProcessedTable(
                                table_id=table_data.get('table_id', f'table_{len(tables)}'),
                                title=table_data.get('title', 'Untitled Table'),
                                description=table_data.get('description', ''),
                                columns=table_data.get('columns', []),
                                rows=table_data.get('rows', []),
                                metadata=table_data.get('metadata', {})
                            )
                            tables.append(table)
                        
                        page = ProcessedPage(
                            page_id=page_data.get('page_id', f'page_{len(processed_pages)}'),
                            title=page_data.get('title', f'Page {len(processed_pages) + 1}'),
                            summary=page_data.get('summary', ''),
                            keywords=page_data.get('keywords', []),
                            tables=tables,
                            raw_content=page_data.get('raw_content', ''),
                            processing_metadata=page_data.get('processing_metadata', {})
                        )
                        processed_pages.append(page)
                    except Exception as page_error:
                        st.warning(f"⚠️ Error loading page {len(processed_pages)}: {str(page_error)}")
                        continue
                
                if not processed_pages:
                    st.error("❌ No valid pages found in the JSON file")
                    return
                
                # Load into session state
                st.session_state.processed_pages = processed_pages
                st.session_state.current_page_idx = 0
                st.session_state.page_statuses = {}
                st.session_state.flagged_pages = set()
                st.session_state.document_folder = result_folder
                st.session_state.current_document = result_folder.name.split('_')[0] + '.pdf'
                st.session_state.processing = False
                # Clear cached PDF path to force re-lookup
                if 'cached_pdf_path' in st.session_state:
                    del st.session_state.cached_pdf_path
                
                st.success(f"📖 Loaded existing results: {len(processed_pages)} pages")
                st.rerun()
            else:
                st.error("❌ Could not find results file")
        except json.JSONDecodeError as json_error:
            st.error(f"❌ Invalid JSON file: {str(json_error)}")
        except Exception as e:
            st.error(f"❌ Error loading results: {str(e)}")
            # Add more detailed error info for debugging
            st.error(f"📋 Debug info: Result folder: {result_folder}")
            if 'data' in locals():
                st.error(f"📋 Data type: {type(data)}, Keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")

    def process_pdf_from_data(self, pdf_path):
        """Process PDF from data directory"""
        try:
            with st.spinner(get_random_message('processing')):
                # Use automatic configuration loading like the original examples
                # The key is to temporarily change directory only for the Sandwich creation
                import os
                original_dir = os.getcwd()
                
                try:
                    # Temporarily change to PB&J directory for config loading
                    os.chdir("peanut_butter_jelly")
                    
                    # Create sandwich (automatically loads config.yaml)
                    sandwich = Sandwich()
                    
                    # Change back immediately to avoid Streamlit issues
                    os.chdir(original_dir)
                    
                    # Process with full path from original directory
                    result = sandwich.process(str(pdf_path))
                    
                except Exception as e:
                    # Ensure we always return to original directory
                    os.chdir(original_dir)
                    raise e
                
                # Load processed data
                document_folder = Path(result['pipeline_info']['document_folder'])
                st.session_state.document_folder = document_folder
                
                # Load final JSON output
                final_output_path = document_folder / "final_output.json"
                if final_output_path.exists():
                    with open(final_output_path, 'r') as f:
                        data = json.load(f)
                    
                    # Handle both old (list) and new (dict with pages key) JSON formats
                    if isinstance(data, list):
                        pages_data = data
                    elif isinstance(data, dict) and 'pages' in data:
                        pages_data = data['pages']
                    else:
                        pages_data = data.get('pages', []) if isinstance(data, dict) else []
                    
                    # Convert to ProcessedPage objects
                    processed_pages = []
                    for page_data in pages_data:
                        tables = []
                        for table_data in page_data.get('tables', []):
                            table = ProcessedTable(
                                table_id=table_data['table_id'],
                                title=table_data['title'],
                                description=table_data['description'],
                                columns=table_data['columns'],
                                rows=table_data['rows'],
                                metadata=table_data['metadata']
                            )
                            tables.append(table)
                        
                        page = ProcessedPage(
                            page_id=page_data['page_id'],
                            title=page_data['title'],
                            summary=page_data['summary'],
                            keywords=page_data['keywords'],
                            tables=tables,
                            raw_content=page_data['raw_content'],
                            processing_metadata=page_data['processing_metadata']
                        )
                        processed_pages.append(page)
                    
                    st.session_state.processed_pages = processed_pages
                    st.session_state.current_page_idx = 0
                    st.session_state.page_statuses = {}
                    st.session_state.flagged_pages = set()
                    st.session_state.current_document = pdf_path.name
                    
                    # Reset processing flag and timer
                    st.session_state.processing = False
                    st.session_state.processing_start_time = None
                    
                    st.success(f"{get_random_message('success')} Processed {len(processed_pages)} pages.")
                    st.rerun()
                else:
                    st.error("❌ Could not find processed output files.")
                    st.session_state.processing = False
                    st.session_state.processing_start_time = None
                    
        except Exception as e:
            st.session_state.processing = False  # Reset flag on error
            st.session_state.processing_start_time = None
            st.error(f"❌ Error processing PDF: {str(e)}")

    def process_pdf(self, uploaded_file):
        """Process uploaded PDF through PB&J pipeline"""
        try:
            with st.spinner(get_random_message('processing')):
                # Save uploaded file temporarily
                temp_pdf_path = f"temp_{uploaded_file.name}"
                with open(temp_pdf_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                
                # Use automatic configuration loading like the original examples
                # The key is to temporarily change directory only for the Sandwich creation
                import os
                original_dir = os.getcwd()
                
                try:
                    # Temporarily change to PB&J directory for config loading
                    os.chdir("peanut_butter_jelly")
                    
                    # Create sandwich (automatically loads config.yaml)
                    sandwich = Sandwich()
                    
                    # Change back immediately to avoid Streamlit issues
                    os.chdir(original_dir)
                    
                    # Process with full path from original directory
                    result = sandwich.process(os.path.join(original_dir, temp_pdf_path))
                    
                except Exception as e:
                    # Ensure we always return to original directory
                    os.chdir(original_dir)
                    raise e
                
                # Load processed data
                document_folder = Path(result['pipeline_info']['document_folder'])
                st.session_state.document_folder = document_folder
                
                # Load final JSON output
                final_output_path = document_folder / "final_output.json"
                if final_output_path.exists():
                    with open(final_output_path, 'r') as f:
                        data = json.load(f)
                    
                    # Handle both old (list) and new (dict with pages key) JSON formats
                    if isinstance(data, list):
                        pages_data = data
                    elif isinstance(data, dict) and 'pages' in data:
                        pages_data = data['pages']
                    else:
                        pages_data = data.get('pages', []) if isinstance(data, dict) else []
                    
                    # Convert to ProcessedPage objects
                    processed_pages = []
                    for page_data in pages_data:
                        tables = []
                        for table_data in page_data.get('tables', []):
                            table = ProcessedTable(
                                table_id=table_data['table_id'],
                                title=table_data['title'],
                                description=table_data['description'],
                                columns=table_data['columns'],
                                rows=table_data['rows'],
                                metadata=table_data['metadata']
                            )
                            tables.append(table)
                        
                        page = ProcessedPage(
                            page_id=page_data['page_id'],
                            title=page_data['title'],
                            summary=page_data['summary'],
                            keywords=page_data['keywords'],
                            tables=tables,
                            raw_content=page_data['raw_content'],
                            processing_metadata=page_data['processing_metadata']
                        )
                        processed_pages.append(page)
                    
                    st.session_state.processed_pages = processed_pages
                    st.session_state.current_page_idx = 0
                    st.session_state.page_statuses = {}
                    st.session_state.flagged_pages = set()
                    st.session_state.current_document = uploaded_file.name
                    
                    # Clean up temp file
                    os.remove(temp_pdf_path)
                    
                    # Reset processing flag and timer
                    st.session_state.processing = False
                    st.session_state.processing_start_time = None
                    
                    st.success(f"{get_random_message('success')} Processed {len(processed_pages)} pages.")
                    st.rerun()
                else:
                    st.error("❌ Could not find processed output files.")
                    st.session_state.processing = False
                    st.session_state.processing_start_time = None
                    
        except Exception as e:
            st.session_state.processing = False  # Reset flag on error
            st.session_state.processing_start_time = None
            st.error(f"❌ Error processing PDF: {str(e)}")
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)

    def render_page_content(self):
        """Render the main page content"""
        if not st.session_state.processed_pages:
            st.markdown("""
            ## 👋 Welcome to the Sandwich Inspector!
            
            Upload a PDF in the sidebar to get started. The app will:
            1. 🥜 **Parse** your PDF with LlamaParse
            2. 🧈 **Enhance** the content with AI
            3. 🍇 **Extract** structured data into tables
            4. 👀 **Present** everything for your review
            
            You can then approve, edit, or flag each page for later review.
            """)
            return
        
        current_page = st.session_state.processed_pages[st.session_state.current_page_idx]
        page_num = st.session_state.current_page_idx + 1
        
        # Page header with navigation
        st.markdown(f"""
        <div class="page-nav">
            <h2>📄 Page {page_num}: {current_page.title}</h2>
            <p><strong>Summary:</strong> {current_page.summary}</p>
            <p><strong>Keywords:</strong> {', '.join(current_page.keywords)}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Main content area with columns
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📖 Original Content")
            
            # Display PDF page if available - Cache the successful path
            if st.session_state.document_folder:
                # Use session state to cache successful PDF path
                if 'cached_pdf_path' not in st.session_state:
                    pdf_candidates = [
                        st.session_state.document_folder / "original.pdf",
                        st.session_state.document_folder / f"temp_{st.session_state.current_document}",
                        st.session_state.document_folder / st.session_state.current_document
                    ]
                    
                    st.session_state.cached_pdf_path = None
                    for candidate in pdf_candidates:
                        if candidate.exists():
                            st.session_state.cached_pdf_path = candidate
                            break
                
                if st.session_state.cached_pdf_path:
                    try:
                        pdf_viewer = PDFViewer(st.session_state.cached_pdf_path)
                        pdf_viewer.render(page_num - 1, show_controls=False)  # Convert to 0-indexed
                    except Exception as e:
                        st.warning(f"Could not display PDF: {str(e)}")
                        st.info("🔍 PDF viewer temporarily unavailable")
                else:
                    st.warning("Original PDF not found")
            
            # Show raw markdown content
            with st.expander("📝 Raw Markdown Content"):
                st.text_area("Raw Content", current_page.raw_content, height=300, disabled=True, label_visibility="collapsed")
        
        with col2:
            st.markdown("### 📊 Extracted Tables")
            
            if current_page.tables:
                for i, table in enumerate(current_page.tables):
                    st.markdown(f"**{table.title}**")
                    if table.description:
                        st.markdown(f"*{table.description}*")
                    
                    # Create sub-columns for table and JSON view
                    table_col, json_col = st.columns([3, 2])
                    
                    with table_col:
                        st.markdown("**📋 Table View**")
                        # Display table
                        if table.rows and table.columns:
                            # Make column names unique for Streamlit data_editor
                            unique_columns = []
                            column_counts = {}
                            
                            for col in table.columns:
                                if col in column_counts:
                                    column_counts[col] += 1
                                    unique_col = f"{col}_{column_counts[col]}"
                                else:
                                    column_counts[col] = 0
                                    unique_col = col
                                unique_columns.append(unique_col)
                            
                            df = pd.DataFrame(table.rows, columns=unique_columns)
                            
                            # FIXED: Remove the condition that prevented editing page 0
                            if st.session_state.edit_mode:
                                # Editable table with validation
                                try:
                                    edited_df = st.data_editor(
                                        df,
                                        key=f"table_{st.session_state.current_page_idx}_{i}",
                                        num_rows="dynamic"
                                    )
                                    # Validate edited data before updating
                                    if edited_df is not None and not edited_df.empty:
                                        # Update the table data (keep original column names)
                                        table.rows = edited_df.values.tolist()
                                    else:
                                        st.warning("⚠️ Invalid table data - changes not saved")
                                except Exception as e:
                                    st.error(f"Error in edit mode: {str(e)}")
                                    st.dataframe(df, use_container_width=True)
                            else:
                                # Read-only table
                                st.dataframe(df, use_container_width=True)
                        else:
                            st.warning("No table data available")
                    
                    with json_col:
                        st.markdown("**🔧 JSON Structure**")
                        # Create structured JSON representation
                        table_json = {
                            "table_id": table.table_id,
                            "title": table.title,
                            "description": table.description,
                            "columns": table.columns,
                            "rows": table.rows,
                            "metadata": table.metadata
                        }
                        
                        # Display JSON with syntax highlighting
                        st.json(table_json)
                        
                        # Add copy button for JSON
                        json_str = json.dumps(table_json, indent=2, ensure_ascii=False)
                        st.code(f"📋 Copy this JSON:\n```json\n{json_str}\n```", language="json")
                    
                    st.markdown("---")
            else:
                st.info("No tables found on this page")
        
        # Action buttons
        st.markdown("### 🎛️ Quality Control")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("✅ Take a Bite (Approve)", use_container_width=True):
                st.session_state.page_statuses[st.session_state.current_page_idx] = 'approved'
                if st.session_state.current_page_idx in st.session_state.flagged_pages:
                    st.session_state.flagged_pages.remove(st.session_state.current_page_idx)
                self.save_current_state()
                st.success("Page approved!")
        
        with col2:
            edit_button_text = "🔧 Stop Editing" if st.session_state.edit_mode else "✏️ Add Seasoning (Edit)"
            if st.button(edit_button_text, use_container_width=True):
                st.session_state.edit_mode = not st.session_state.edit_mode
                st.rerun()
        
        with col3:
            if st.button("🚩 Save for Later (Flag)", use_container_width=True):
                st.session_state.flagged_pages.add(st.session_state.current_page_idx)
                if st.session_state.current_page_idx in st.session_state.page_statuses:
                    del st.session_state.page_statuses[st.session_state.current_page_idx]
                self.save_current_state()
                st.warning("Page flagged for review!")
        
        with col4:
            if st.button("💾 Save Recipe (Export)", use_container_width=True):
                self.export_final_json()
        
        # Edit mode indicator
        if st.session_state.edit_mode:
            st.info("🔧 Edit mode is ON. Modify tables above and they will auto-save when you navigate or export.")

    def save_current_state(self):
        """Save current state to the JSON files"""
        if not st.session_state.document_folder or not st.session_state.processed_pages:
            return
        
        try:
            # Convert processed pages back to dict format
            pages_data = []
            for page in st.session_state.processed_pages:
                tables_data = []
                for table in page.tables:
                    table_dict = {
                        'table_id': table.table_id,
                        'title': table.title,
                        'description': table.description,
                        'columns': table.columns,
                        'rows': table.rows,
                        'metadata': table.metadata
                    }
                    tables_data.append(table_dict)
                
                page_dict = {
                    'page_id': page.page_id,
                    'title': page.title,
                    'summary': page.summary,
                    'keywords': page.keywords,
                    'tables': tables_data,
                    'raw_content': page.raw_content,
                    'processing_metadata': page.processing_metadata
                }
                pages_data.append(page_dict)
            
            # FIXED: Consistent JSON structure - always wrap pages in proper structure
            final_json_structure = {
                'document_info': {
                    'document_name': st.session_state.current_document.replace('.pdf', '').replace('temp_', ''),
                    'original_pdf': st.session_state.current_document,
                    'last_updated': datetime.now().isoformat(),
                    'total_pages': len(pages_data),
                    'total_tables': sum(len(page.get('tables', [])) for page in pages_data)
                },
                'pages': pages_data
            }
            
            # Save updated JSON with consistent structure
            final_output_path = st.session_state.document_folder / "final_output.json"
            with open(final_output_path, 'w') as f:
                json.dump(final_json_structure, f, indent=2, ensure_ascii=False)
            
            # Save inspector metadata
            inspector_metadata = {
                'page_statuses': st.session_state.page_statuses,
                'flagged_pages': list(st.session_state.flagged_pages),
                'last_updated': datetime.now().isoformat(),
                'document_name': st.session_state.current_document
            }
            
            metadata_path = st.session_state.document_folder / "inspector_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(inspector_metadata, f, indent=2)
                
        except Exception as e:
            st.error(f"Error saving state: {str(e)}")
            # Add recovery mechanism
            st.warning("💾 Attempting to create backup...")
            try:
                backup_path = st.session_state.document_folder / f"backup_final_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(backup_path, 'w') as f:
                    json.dump({'pages': pages_data}, f, indent=2)
                st.info(f"✅ Backup saved to {backup_path.name}")
            except:
                st.error("❌ Could not create backup")

    def export_final_json(self):
        """Export the final corrected JSON"""
        self.save_current_state()
        
        if st.session_state.document_folder:
            final_path = st.session_state.document_folder / "final_output.json"
            if final_path.exists():
                with open(final_path, 'r') as f:
                    data = f.read()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="📥 Download Final JSON",
                        data=data,
                        file_name=f"corrected_{st.session_state.current_document}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                
                with col2:
                    if st.button("🏁 Create Final Output Folder", use_container_width=True):
                        self.create_final_output_folder()
                
                st.success("🎉 Recipe saved and ready for download!")
            else:
                st.error("No final output file found")

    def create_final_output_folder(self):
        """Create a clean final output folder with non-temporary names"""
        if not st.session_state.document_folder or not st.session_state.processed_pages:
            st.error("No processed data to export")
            return
        
        try:
            # Create final output directory
            original_doc_name = st.session_state.current_document
            clean_doc_name = original_doc_name.replace('.pdf', '').replace('temp_', '')
            
            final_output_dir = Path("final_outputs") / f"{clean_doc_name}_final"
            final_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. Save clean final JSON
            self.save_current_state()  # Ensure latest changes are saved
            
            # Load the current final_output.json and enhance it
            source_json_path = st.session_state.document_folder / "final_output.json"
            if source_json_path.exists():
                with open(source_json_path, 'r') as f:
                    json_data = json.load(f)
                
                # Add final export metadata
                if isinstance(json_data, list):
                    # If it's just a list of pages, wrap it in a proper structure
                    enhanced_data = {
                        "document_info": {
                            "document_name": clean_doc_name,
                            "original_pdf": original_doc_name,
                            "final_export_date": datetime.now().isoformat(),
                            "total_pages": len(json_data),
                            "total_tables": sum(len(page.get('tables', [])) for page in json_data),
                            "review_status": {
                                "approved_pages": len([i for i in st.session_state.page_statuses.values() if i == 'approved']),
                                "flagged_pages": len(st.session_state.flagged_pages),
                                "total_reviewed": len(st.session_state.page_statuses) + len(st.session_state.flagged_pages)
                            }
                        },
                        "pages": json_data
                    }
                else:
                    enhanced_data = json_data
                    # Add or update document info
                    if "document_info" not in enhanced_data:
                        enhanced_data["document_info"] = {}
                    enhanced_data["document_info"].update({
                        "document_name": clean_doc_name,
                        "original_pdf": original_doc_name,
                        "final_export_date": datetime.now().isoformat(),
                        "review_status": {
                            "approved_pages": len([i for i in st.session_state.page_statuses.values() if i == 'approved']),
                            "flagged_pages": len(st.session_state.flagged_pages),
                            "total_reviewed": len(st.session_state.page_statuses) + len(st.session_state.flagged_pages)
                        }
                    })
                
                # Save enhanced final JSON
                final_json_path = final_output_dir / f"{clean_doc_name}_final.json"
                with open(final_json_path, 'w') as f:
                    json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
            
            # 2. Generate and save final markdown summary
            markdown_content = self.generate_final_markdown_summary()
            final_md_path = final_output_dir / f"{clean_doc_name}_summary.md"
            with open(final_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 3. Save individual page markdown files
            pages_dir = final_output_dir / "pages"
            pages_dir.mkdir(exist_ok=True)
            
            for i, page in enumerate(st.session_state.processed_pages):
                page_md_content = f"# Page {i+1}: {page.title}\n\n"
                page_md_content += f"**Summary:** {page.summary}\n\n"
                page_md_content += f"**Keywords:** {', '.join(page.keywords)}\n\n"
                
                if page.tables:
                    page_md_content += "## Tables\n\n"
                    for j, table in enumerate(page.tables):
                        page_md_content += f"### {table.title}\n\n"
                        if table.description:
                            page_md_content += f"*{table.description}*\n\n"
                        
                        if table.rows and table.columns:
                            # Create markdown table
                            page_md_content += "| " + " | ".join(table.columns) + " |\n"
                            page_md_content += "| " + " | ".join(["---"] * len(table.columns)) + " |\n"
                            for row in table.rows:
                                page_md_content += "| " + " | ".join(str(cell) for cell in row) + " |\n"
                            page_md_content += "\n"
                
                page_md_content += "## Raw Content\n\n"
                page_md_content += page.raw_content
                
                page_file_path = pages_dir / f"page_{i+1:02d}_{page.title.replace(' ', '_').replace('/', '_')}.md"
                with open(page_file_path, 'w', encoding='utf-8') as f:
                    f.write(page_md_content)
            
            # 4. Copy original PDF if available
            if st.session_state.document_folder:
                # Try to find and copy the original PDF
                pdf_candidates = [
                    st.session_state.document_folder / "original.pdf",
                    st.session_state.document_folder / f"temp_{st.session_state.current_document}",
                    st.session_state.document_folder / st.session_state.current_document,
                    Path("data") / original_doc_name
                ]
                
                for pdf_candidate in pdf_candidates:
                    if pdf_candidate.exists():
                        final_pdf_path = final_output_dir / f"{clean_doc_name}.pdf"
                        import shutil
                        shutil.copy2(pdf_candidate, final_pdf_path)
                        break
            
            # 5. Save final export report
            export_report = {
                "export_info": {
                    "export_date": datetime.now().isoformat(),
                    "original_document": original_doc_name,
                    "clean_document_name": clean_doc_name,
                    "final_output_directory": str(final_output_dir),
                    "files_created": [
                        f"{clean_doc_name}_final.json",
                        f"{clean_doc_name}_summary.md",
                        f"{clean_doc_name}.pdf",
                        "pages/ (individual page markdown files)"
                    ]
                },
                "review_summary": {
                    "total_pages": len(st.session_state.processed_pages),
                    "approved_pages": len([i for i in st.session_state.page_statuses.values() if i == 'approved']),
                    "flagged_pages": len(st.session_state.flagged_pages),
                    "total_tables": sum(len(page.tables) for page in st.session_state.processed_pages),
                    "page_statuses": st.session_state.page_statuses,
                    "flagged_page_indices": list(st.session_state.flagged_pages)
                }
            }
            
            export_report_path = final_output_dir / "export_report.json"
            with open(export_report_path, 'w') as f:
                json.dump(export_report, f, indent=2)
            
            st.success(f"""
            🎉 **Final Output Created Successfully!**
            
            **Location:** `{final_output_dir}`
            
            **Files Created:**
            - 📊 `{clean_doc_name}_final.json` - Final structured data with your edits
            - 📝 `{clean_doc_name}_summary.md` - Complete document summary  
            - 📄 `{clean_doc_name}.pdf` - Original PDF (if found)
            - 📁 `pages/` - Individual page markdown files
            - 📋 `export_report.json` - Export and review summary
            
            **Review Status:**
            - ✅ Approved: {len([i for i in st.session_state.page_statuses.values() if i == 'approved'])} pages
            - 🚩 Flagged: {len(st.session_state.flagged_pages)} pages  
            - 📊 Total Tables: {sum(len(page.tables) for page in st.session_state.processed_pages)}
            """)
            
        except Exception as e:
            st.error(f"❌ Error creating final output folder: {str(e)}")

    def generate_final_markdown_summary(self):
        """Generate a comprehensive markdown summary of the entire document"""
        if not st.session_state.processed_pages:
            return "No processed pages available."
        
        # Header
        doc_name = st.session_state.current_document.replace('.pdf', '').replace('temp_', '')
        content = f"# {doc_name} - Processing Summary\n\n"
        content += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Overall stats
        total_tables = sum(len(page.tables) for page in st.session_state.processed_pages)
        approved_count = len([i for i in st.session_state.page_statuses.values() if i == 'approved'])
        flagged_count = len(st.session_state.flagged_pages)
        
        content += "## 📊 Document Overview\n\n"
        content += f"- **Total Pages:** {len(st.session_state.processed_pages)}\n"
        content += f"- **Total Tables:** {total_tables}\n"
        content += f"- **Approved Pages:** {approved_count}\n"
        content += f"- **Flagged Pages:** {flagged_count}\n"
        content += f"- **Review Progress:** {((approved_count + flagged_count) / len(st.session_state.processed_pages) * 100):.1f}%\n\n"
        
        # Combined keywords
        all_keywords = set()
        for page in st.session_state.processed_pages:
            all_keywords.update(page.keywords)
        
        content += "## 🔍 Key Topics\n\n"
        content += ", ".join(sorted(all_keywords))
        content += "\n\n"
        
        # Page-by-page summary
        content += "## 📄 Page-by-Page Summary\n\n"
        for i, page in enumerate(st.session_state.processed_pages):
            page_num = i + 1
            status = "🚩 Flagged" if i in st.session_state.flagged_pages else ("✅ Approved" if st.session_state.page_statuses.get(i) == 'approved' else "⏳ Pending")
            
            content += f"### Page {page_num}: {page.title} {status}\n\n"
            content += f"**Summary:** {page.summary}\n\n"
            
            if page.tables:
                content += f"**Tables ({len(page.tables)}):**\n"
                for table in page.tables:
                    content += f"- {table.title}\n"
                content += "\n"
            else:
                content += "**Tables:** None\n\n"
            
            content += f"**Keywords:** {', '.join(page.keywords)}\n\n"
            content += "---\n\n"
        
        # Table details
        if total_tables > 0:
            content += "## 📋 Table Details\n\n"
            table_counter = 1
            for i, page in enumerate(st.session_state.processed_pages):
                for table in page.tables:
                    content += f"### Table {table_counter}: {table.title}\n\n"
                    content += f"**Page:** {i+1}\n\n"
                    if table.description:
                        content += f"**Description:** {table.description}\n\n"
                    
                    if table.rows and table.columns:
                        content += f"**Structure:** {len(table.columns)} columns × {len(table.rows)} rows\n\n"
                        content += f"**Columns:** {', '.join(table.columns)}\n\n"
                        
                        # Show first few rows as example
                        content += "**Sample Data:**\n\n"
                        content += "| " + " | ".join(table.columns) + " |\n"
                        content += "| " + " | ".join(["---"] * len(table.columns)) + " |\n"
                        for row in table.rows[:3]:  # Show first 3 rows
                            content += "| " + " | ".join(str(cell) for cell in row) + " |\n"
                        if len(table.rows) > 3:
                            content += f"| ... | ... | (and {len(table.rows)-3} more rows) |\n"
                        content += "\n"
                    
                    content += "---\n\n"
                    table_counter += 1
        
        return content

    def run(self):
        """Main app runner"""
        self.render_header()
        self.render_sidebar()
        self.render_page_content()

# Main execution
if __name__ == "__main__":
    inspector = SandwichInspector()
    inspector.run() 