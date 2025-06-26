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

from pdf_utils import PDFViewer
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

    def render_header(self):
        """Render the main header"""
        st.markdown("""
        <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #667eea, #764ba2); color: white; border-radius: 10px; margin-bottom: 30px;">
            <h1 style="margin: 0; font-size: 2.5em;">🔍 Document Accuracy Inspector</h1>
            <p style="margin: 10px 0 0 0; font-size: 1.2em;">Verify extracted data against original PDFs</p>
        </div>
        """, unsafe_allow_html=True)

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
                
                # Create display names with timestamps
                folder_options = []
                for folder in document_folders:
                    folder_name = folder.name
                    # Extract timestamp from folder name if available
                    parts = folder_name.split('_')
                    if len(parts) >= 3:
                        try:
                            date_part = parts[-2]
                            time_part = parts[-1]
                            date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                            time_str = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                            display_name = f"{parts[0]} ({date_str} {time_str})"
                        except (IndexError, ValueError):
                            display_name = folder_name
                    else:
                        display_name = folder_name
                    folder_options.append((display_name, folder))
                
                # Document selection
                selected_option = st.sidebar.selectbox(
                    "Select document to review:",
                    range(len(folder_options)),
                    format_func=lambda i: folder_options[i][0],
                    help="Choose a processed document to review and edit"
                )
                
                if selected_option is not None:
                    selected_folder = folder_options[selected_option][1]
                    
                    # Load document button
                    if st.sidebar.button("📖 Load Document", use_container_width=True):
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
            pending = max(0, total_pages - approved - flagged)  # Ensure non-negative
            
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
            json_folder = document_folder / "03_cleaned_json"
            markdown_folder = document_folder / "02_enhanced_markdown"
            
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
            
            # Extract pages from the new structure
            pages_data = final_data.get('pages', [])
            if not pages_data:
                st.error("❌ No pages found in final_output.json")
                return
            
            # Convert to ProcessedPage objects
            processed_pages = []
            for i, page_data in enumerate(pages_data):
                try:
                    # Get page content - try different field names for compatibility
                    page_content = page_data.get('raw_content', page_data.get('content', ''))
                    
                    # Load corresponding markdown file if available (optional)
                    markdown_folder = document_folder / "02_enhanced_markdown"
                    if markdown_folder.exists():
                        markdown_file = markdown_folder / f"page_{i+1}.md"
                        if markdown_file.exists():
                            try:
                                with open(markdown_file, 'r', encoding='utf-8') as f:
                                    markdown_content = f.read()
                                # Use markdown file content if it exists and is longer
                                if len(markdown_content.strip()) > len(page_content.strip()):
                                    page_content = markdown_content
                            except Exception:
                                pass
                    
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
                        title=page_data.get('title', f'Page {i+1}'),
                        content=page_content,
                        tables=tables,
                        keywords=page_data.get('keywords', [])
                    )
                    processed_pages.append(page)
                    
                except Exception as e:
                    st.error(f"❌ Error loading page {i+1}: {e}")
                    continue
            
            if processed_pages:
                self._finalize_document_loading(document_folder, processed_pages)
            else:
                st.error("❌ No pages could be loaded from the document")
                
        except Exception as e:
            st.error(f"❌ Error reading final_output.json: {e}")

    def _load_from_individual_files(self, document_folder, json_folder, markdown_folder):
        """Load document from old individual file structure (backward compatibility)"""
        try:
            # Load all page JSONs and markdowns
            json_files = sorted(json_folder.glob("page_*.json"))
            markdown_files = sorted(markdown_folder.glob("page_*.md"))
            
            if not json_files:
                st.error(f"❌ No page JSON files found in {document_folder.name}")
                return
                
            # Convert to ProcessedPage objects
            processed_pages = []
            for i, json_file in enumerate(json_files):
                try:
                    with open(json_file, 'r') as f:
                        page_data = json.load(f)
                    
                    # Load corresponding markdown if available
                    markdown_content = ""
                    if i < len(markdown_files):
                        try:
                            with open(markdown_files[i], 'r') as f:
                                markdown_content = f.read()
                        except Exception:
                            pass
                    
                    # Create ProcessedTable objects - handle empty tables gracefully
                    tables = []
                    table_data_list = page_data.get('tables', [])
                    
                    # Only process if there are actual tables
                    if table_data_list and isinstance(table_data_list, list):
                        for table_data in table_data_list:
                            # Ensure table_data is a dictionary
                            if isinstance(table_data, dict):
                                # Tables are in old "data" format (list of dictionaries)
                                data = table_data.get('data', [])
                                
                                # Only create table if there's actual data
                                if data and isinstance(data, list) and len(data) > 0:
                                    table = ProcessedTable(
                                        title=table_data.get('title', 'Untitled Table'),
                                        data=data
                                    )
                                    tables.append(table)
                    
                    # Create ProcessedPage object
                    page = ProcessedPage(
                        title=page_data.get('title', f'Page {i+1}'),
                        content=markdown_content,
                        tables=tables,
                        keywords=page_data.get('keywords', [])
                    )
                    processed_pages.append(page)
                    
                except Exception as e:
                    st.error(f"❌ Error loading page {i+1}: {e}")
                    continue
            
            if processed_pages:
                self._finalize_document_loading(document_folder, processed_pages)
            else:
                st.error("❌ No pages could be loaded from the document")
                
        except Exception as e:
            st.error(f"❌ Error loading from individual files: {e}")

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
        page_num = st.session_state.current_page_idx + 1
        
        # Page status indicator
        page_status = st.session_state.page_statuses.get(st.session_state.current_page_idx, 'pending')
        status_icon = "✅" if page_status == 'approved' else "🚩" if st.session_state.current_page_idx in st.session_state.flagged_pages else "⏳"
        
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #f0f2f6, #ffffff); padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #e6e9ef;">
            <h3 style="margin: 0; color: #262730;">
                {status_icon} Page {page_num}/{len(st.session_state.processed_pages)}: {current_page.title}
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
            
            # Display PDF page
            if st.session_state.document_folder:
                folder_name = st.session_state.document_folder.name
                doc_name = folder_name.split('_')[0]
                pdf_path = st.session_state.document_folder / f"{doc_name}.pdf"
                
                if pdf_path.exists():
                    try:
                        pdf_viewer = PDFViewer(pdf_path)
                        pdf_viewer.render(page_num - 1, show_controls=False)
                    except Exception as e:
                        st.error(f"Could not display PDF: {str(e)}")
                else:
                    st.error(f"PDF not found: {pdf_path}")
        
        with data_col:
            st.markdown("### 🔍 Extracted Data - Verify Accuracy")
            
            # Check what data we have
            has_tables = current_page.tables and len(current_page.tables) > 0
            has_content = current_page.content and current_page.content.strip()
            
            # Determine tab structure
            if has_tables and has_content:
                tab_labels = ["📊 Tables", "📝 Markdown"]
            elif has_tables:
                tab_labels = ["📊 Tables"]
            elif has_content:
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
                                            table.data = edited_table_data['data']
                                            if 'title' in edited_table_data:
                                                table.title = edited_table_data['title']
                                            st.success("✅ JSON updated successfully!")
                                except json.JSONDecodeError as e:
                                    st.error(f"❌ Invalid JSON: {str(e)}")
                                except Exception as e:
                                    st.error(f"❌ Error updating table: {str(e)}")
                            else:
                                # View mode: Show table normally
                                df = pd.DataFrame(table.data)
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
            if has_content:
                markdown_container = tabs[tab_idx] if len(tab_labels) > 1 else tabs[0]
                
                with markdown_container:
                    if st.session_state.edit_mode:
                        st.info("🔧 **EDIT MODE**: Review and correct the markdown content")
                        edited_content = st.text_area(
                            "Markdown content:",
                            current_page.content,
                            height=500,
                            key=f"markdown_editor_{st.session_state.current_page_idx}",
                            help="Edit the markdown to match the PDF content exactly"
                        )
                        # Update content if changed
                        if edited_content != current_page.content:
                            current_page.content = edited_content
                    else:
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
            
            # Handle case where there's no tabular data and no meaningful content
            if not has_tables and not has_content:
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
            if st.button("🚩 Flag Issues", use_container_width=True):
                st.session_state.flagged_pages.add(st.session_state.current_page_idx)
                if st.session_state.current_page_idx in st.session_state.page_statuses:
                    del st.session_state.page_statuses[st.session_state.current_page_idx]
                self.save_current_state()
                st.warning("🚩 Page flagged for review")
        
        with button_col4:
            if st.button("💾 Save Changes", use_container_width=True):
                self.save_current_state()
                st.success("💾 Changes saved!")
        
        with button_col5:
            if st.button("🏁 Export Final", use_container_width=True):
                self.create_final_output_folder()
        
        # Status indicator
        if st.session_state.edit_mode:
            st.info("🔧 **EDIT MODE ACTIVE** - Make your corrections above, they auto-save when you navigate or export.")
        
        # Quick navigation
        if len(st.session_state.processed_pages) > 1:
            st.markdown("### ⏭️ Quick Navigation")
            nav_cols = st.columns(min(len(st.session_state.processed_pages), 10))
            
            for i in range(len(st.session_state.processed_pages)):
                if i < 10:  # Limit to 10 buttons
                    col_idx = i % len(nav_cols)
                    with nav_cols[col_idx]:
                        status = st.session_state.page_statuses.get(i, 'pending')
                        icon = "✅" if status == 'approved' else "🚩" if i in st.session_state.flagged_pages else "⏳"
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
            return
        
        try:
            # Check which format we're working with
            final_output_file = st.session_state.document_folder / "final_output.json"
            
            if final_output_file.exists():
                # Save back to final_output.json format
                self._save_to_final_output(final_output_file)
            else:
                # Save back to individual files format
                self._save_to_individual_files()
            
            # Always save inspector metadata
            self._save_inspector_metadata()
                
        except Exception as e:
            st.error(f"Error saving state: {str(e)}")

    def _save_to_final_output(self, final_output_file):
        """Save changes back to final_output.json format"""
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
            
            # Save the updated final_output.json
            with open(final_output_file, 'w') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            st.error(f"Error saving to final_output.json: {str(e)}")

    def _save_to_individual_files(self):
        """Save changes back to individual file format (backward compatibility)"""
        try:
            # Save back to the individual page JSON files in 03_cleaned_json
            json_folder = st.session_state.document_folder / "03_cleaned_json"
            
            for i, page in enumerate(st.session_state.processed_pages):
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
            
                # Save individual page JSON
                page_file = json_folder / f"page_{i+1}.json"
                with open(page_file, 'w') as f:
                    json.dump(page_data, f, indent=2, ensure_ascii=False)
            
            # Also save back to enhanced markdown files
            markdown_folder = st.session_state.document_folder / "02_enhanced_markdown"
            for i, page in enumerate(st.session_state.processed_pages):
                markdown_file = markdown_folder / f"page_{i+1}.md"
                with open(markdown_file, 'w', encoding='utf-8') as f:
                    # Handle empty content gracefully
                    content_to_save = page.content if page.content else ""
                    f.write(content_to_save)
                    
        except Exception as e:
            st.error(f"Error saving to individual files: {str(e)}")

    def _save_inspector_metadata(self):
        """Save inspector metadata (common for both formats)"""
        try:
            # Save inspector metadata (including portfolio tag)
            inspector_metadata = {
                'page_statuses': st.session_state.page_statuses,
                'flagged_pages': list(st.session_state.flagged_pages),
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
                        "flagged_pages": len(st.session_state.flagged_pages)
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
            - 📊 Total Tables: {sum(len(page.tables) for page in st.session_state.processed_pages)}{portfolio_info}
            """)
            
        except Exception as e:
            st.error(f"❌ Error creating final output folder: {str(e)}")

    def run(self):
        """Main app runner"""
        self.render_header()
        self.render_sidebar()
        self.render_page_content()

# Main execution
if __name__ == "__main__":
    inspector = SandwichInspector()
    inspector.run() 