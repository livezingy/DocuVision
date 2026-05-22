# core/processing/page_processor.py
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image
import time, os, io
from docuvision_core.processing.base_processor import BaseProcessor
from docuvision_core.processing.table_processor import TableProcessor
from docuvision_core.utils.logger import AppLogger
from concurrent.futures import ThreadPoolExecutor
import pdfplumber
import numpy as np
from docuvision_core.utils.path_utils import get_output_subpath
import fitz  # PyMuPDF for image extraction

class PageProcessor(BaseProcessor):

    """Page processor class

    Responsible for text extraction and table recognition in documents.
    Integrates OCR and table processing capabilities.
    """
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize text processor
        
        Args:
            params: Processing parameters
        """
        super().__init__()
        self.logger = AppLogger.get_logger()
        # 不再需要self.config
        self.params = params or {}

    def _is_scanned_pdf(self, pdfplumber_object, page_num: int) -> bool:
        """检测PDF页面是否为扫描文桀
        
        改进版：使用多维度综合判方
        1. 文本密度（动态阈值）
        2. 矢量对象数量
        3. 最大图像占毀
        
        Args:
            pdfplumber_object: pdfplumber PDF对象
            page_num: 页面编号（从1开始）
            
        Returns:
            bool: True表示扫描PDF，False表示文本PDF
        """
        try:
            page = pdfplumber_object.pages[page_num - 1]
            page_area = page.width * page.height
            
            # ========== 检柀：文本密度（动态阈值） ==========
            text = page.extract_text()
            text_length = len(text.strip()) if text else 0
            
            # 动态阈值：基于页面面积计算
            # A4页面(595x842)标准文本密度纀.002-0.006字符/平方炀
            min_text_threshold = max(30, page_area * 0.0005)
            
            if text_length < min_text_threshold:
                # ========== 检柀：矢量对象数里==========
                # 扫描PDF通常没有矢量对象
                lines = page.lines if hasattr(page, 'lines') else []
                rects = page.rects if hasattr(page, 'rects') else []
                curves = page.curves if hasattr(page, 'curves') else []
                
                vector_count = len(lines) + len(rects) + len(curves)
                
                # 如果文本少且矢量对象也少，判定为扫描PDF
                if vector_count < 10:
                    self.logger.info(
                        f"Page {page_num}: 扫描PDF (文本:{text_length:.0f}/{min_text_threshold:.0f}, "
                        f"矢量对象:{vector_count})"
                    )
                    return True
            
            # ========== 检柀：最大图像占毀==========
            images = page.images if hasattr(page, 'images') else []
            
            if images:
                # 使用max()找到面积最大的图像，O(n)复杂庀
                largest_image = max(
                    images, 
                    key=lambda img: abs(img.get('x1', 0) - img.get('x0', 0)) * 
                                   abs(img.get('bottom', 0) - img.get('top', 0))
                )
                
                # 计算最大图像的面积
                largest_area = (
                    abs(largest_image.get('x1', 0) - largest_image.get('x0', 0)) * 
                    abs(largest_image.get('bottom', 0) - largest_image.get('top', 0))
                )
                
                largest_ratio = largest_area / page_area if page_area > 0 else 0
                
                # 如果最大图像占比超过0%，判定为扫描PDF
                if largest_ratio > 0.7:
                    self.logger.info(
                        f"Page {page_num}: 扫描PDF (最大图像占毀{largest_ratio:.1%}, "
                        f"面积 {largest_area:.0f}/{page_area:.0f})"
                    )
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting scanned PDF for page {page_num}: {e}")
            return False

    async def _process_with_transformer(self, image, params):
        """使用Transformer处理图像
        
        Args:
            image: PIL Image对象
            params: 处理参数
            
        Returns:
            dict: 处理结果
        """
        table_parser = params.get('table_parser')
        
        # 如果没有提供table_parser，尝试创廀
        if not table_parser:
            try:
                from docuvision_core.models.table_parser import TableParser
                from docuvision_core.utils.config import load_config
                app_config = load_config()
                table_parser = TableParser(app_config)
                self.logger.info("[PageProcessor] Created TableParser instance")
            except Exception as e:
                self.logger.error(f"[PageProcessor] Failed to create TableParser: {str(e)}")
                return {'success': False, 'error': f'Failed to create TableParser: {str(e)}', 'tables': []}
        
        if table_parser and hasattr(table_parser, 'parser_image'):
            self.logger.info("[PageProcessor] Using Transformer for image processing")
            try:
                if not hasattr(table_parser, 'models') or table_parser.models is None:
                    self.logger.error("[PageProcessor] TableParser models not initialized")
                    return {'success': False, 'error': 'TableParser models not initialized', 'tables': []}
                else:
                    results = await table_parser.parser_image(image, params)
                    return results
            except Exception as e:
                self.logger.error(f"[PageProcessor] Error calling table_parser.parser_image: {str(e)}")
                return {'success': False, 'error': str(e), 'tables': []}
        else:
            self.logger.error("[PageProcessor] table_parser not found in params or missing parser_image method")
            return {'success': False, 'error': 'table_parser not available', 'tables': []}

    async def _process_page_as_scanned(self, page, params):
        """将PDF页面转为图像后用Transformer处理
        
        Args:
            page: pdfplumber页面对象
            params: 处理参数
            
        Returns:
            dict: 处理结果
        """
        try:
            # 将PDF页面转换为图像，提高分辨率以获得更好的OCR效果
            image = page.to_image(resolution=300)  # 提高分00 DPI
            pil_image = Image.frombytes('RGB', image.original.size, image.original.tobytes())
            
            self.logger.info(f"[PageProcessor] Converted PDF page to image for Transformer processing (resolution: 300 DPI, size: {pil_image.size})")
            return await self._process_with_transformer(pil_image, params)
            
        except Exception as e:
            self.logger.error(f"[PageProcessor] Error converting page to image: {str(e)}")
            return {'success': False, 'error': str(e), 'tables': []}

    async def _process_with_auto_flavor(self, page, method, params):
        """Auto模式：自动选择flavor
        
        Args:
            page: pdfplumber页面对象
            method: 提取方法
            params: 处理参数
            
        Returns:
            dict: 处理结果
        """
        from docuvision_core.processing.table_processor import PageFeatureAnalyzer
        
        try:
            # 创建特征分析器（禁用详细日志，避免重复输出）
            analyzer = PageFeatureAnalyzer(page)
            
            # 预测表格类型
            table_type = analyzer.predict_table_type()
            
            # 根据方法和类型选择flavor
            if method == 'camelot':
                flavor = 'lattice' if table_type == 'bordered' else 'stream'
            elif method == 'pdfplumber':
                flavor = 'lines' if table_type == 'bordered' else 'text'
            else:
                flavor = 'auto'  # 保持原倀
            
            self.logger.info(f"[PageProcessor] Auto mode: detected {table_type} table, selected {flavor} method")
            
            # 调用标准处理
            return await self._process_with_method(page, method, flavor, params)
            
        except Exception as e:
            self.logger.error(f"[PageProcessor] Error in auto flavor selection: {str(e)}")
            return {'success': False, 'error': str(e), 'tables': []}

    async def _process_with_method(self, page, method, flavor, params):
        """使用指定方法和flavor处理页面
        
        Args:
            page: pdfplumber页面对象
            method: 提取方法
            flavor: 提取flavor
            params: 处理参数
            
        Returns:
            dict: 处理结果
        """
        try:
            table_processor = TableProcessor(params)
            pdf_path = params.get('current_filepath')
            
            if method == 'camelot':
                page_num = getattr(page, 'page_number', 1)
                # 使用新的提取器接又
                from docuvision_core.processing.table_processor import PageFeatureAnalyzer
                analyzer = PageFeatureAnalyzer(page, enable_logging=False)
                results = table_processor._process_camelot(pdf_path, page, analyzer, flavor, params.get('table_score_threshold', 0.5))
            elif method == 'pdfplumber':
                # 使用新的提取器接又
                from docuvision_core.processing.table_processor import PageFeatureAnalyzer
                analyzer = PageFeatureAnalyzer(page, enable_logging=False)
                results = table_processor._process_pdfplumber(page, analyzer, flavor, params.get('table_score_threshold', 0.5))
            elif method == 'transformer':
                # Transformer需要将页面转为图像
                return await self._process_page_as_scanned(page, params)
            else:
                self.logger.error(f"[PageProcessor] Unknown method: {method}")
                return {'success': False, 'error': f'Unknown method: {method}', 'tables': []}
            
            return {'success': True, 'tables': results, 'error': ''}
            
        except Exception as e:
            self.logger.error(f"[PageProcessor] Error in method processing: {str(e)}")
            return {'success': False, 'error': str(e), 'tables': []}

    async def process(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process PDF or image file"""
        try:
            params = params.copy() if params else self.params.copy()
            file_path = params.get('current_filepath')
            self.logger.info(f"[PageProcessor] Starting document processing: {file_path}")
            ext = os.path.splitext(file_path)[1].lower()
            self.logger.debug(f"[PageProcessor] File extension: {ext}")
            self.logger.debug(f"[PageProcessor] Params: {params}")

            results = {'tables': [], 'error': "", 'pages': []}

            # 1. 处理图像文件
            if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff']:
                self.logger.info("[PageProcessor] Detected image file, using Transformer")
                image = Image.open(file_path)
                if image.mode != "RGB":
                    image = image.convert("RGB")
                
                # 添加页面号信息（图像文件默认为第1页）
                params['current_page_num'] = 1
                results = await self._process_with_transformer(image, params)
                
                # Export results if needed (same logic as PDF processing)
                if params.get('export_results', True) and results.get('tables'):
                    try:
                        self.logger.info("[PageProcessor] Exporting Transformer results")
                        export_path = self._handle_export(results, params)
                        results['export_path'] = export_path
                    except Exception as e:
                        self.logger.error(f"[PageProcessor] Transformer export failed: {str(e)}")
                
                return {
                    'success': results.get('success', True),
                    'tables': results.get('tables', []) if isinstance(results, dict) else [],
                    'export_path': results.get('export_path', None),
                    'pages': [],
                    'error': results.get('error', '') if isinstance(results, dict) else ''
                }

            # 2. 处理PDF文件
            self.logger.info("[PageProcessor] Detected PDF file, starting pdfplumber open")
            pages = params.get('pages', 'all')
            # Treat empty or whitespace pages as 'all'
            if pages is None or str(pages).strip() == "":
                pages = 'all'
            
            page_list = []
            try:
                with pdfplumber.open(file_path) as pdfplumber_object:
                    self.logger.info("[PageProcessor] PDF opened successfully")
                    if not hasattr(pdfplumber_object, 'pages') or not pdfplumber_object.pages:
                        self.logger.error("No pages found in PDF.")
                        return {
                            'success': False,
                            'tables': [],
                            'export_path': None,
                            'pages': [],
                            'error': "No pages found in PDF."
                        }
                    
                    # 解析页面列表
                    if pages == 'all':
                        try:
                            page_list = list(range(1, len(pdfplumber_object.pages) + 1))
                            self.logger.info(f"[PageProcessor] Processing all pages: {page_list}")
                        except Exception as e:
                            self.logger.error(f"[PageProcessor] Failed to get total pages: {str(e)}")
                            return {
                                'success': False,
                                'tables': [],
                                'export_path': None,
                                'pages': [],
                                'error': str(e)
                            }
                    else:
                        try:
                            page_list = []
                            for part in str(pages).split(','):
                                part = part.strip()
                                if '-' in part:
                                    start, end = part.split('-')
                                    page_list.extend(list(range(int(start), int(end)+1)))
                                elif part:
                                    page_list.append(int(part))
                            page_list = sorted(set(page_list))
                            if not page_list:
                                # Fallback to all pages when custom input is empty/invalid
                                page_list = list(range(1, len(pdfplumber_object.pages) + 1))
                                self.logger.info("[PageProcessor] Empty custom pages, fallback to all pages")
                            else:
                                self.logger.info(f"[PageProcessor] Custom page list: {page_list}")
                        except Exception as e:
                            self.logger.error(f"[PageProcessor] Invalid pages parameter: {pages}, error: {str(e)}")
                            return {
                                'success': False,
                                'tables': [],
                                'export_path': None,
                                'pages': [],
                                'error': f'Invalid pages parameter: {pages}'
                            }

                    # 处理每个页面
                    for page_num in page_list:
                        try:
                            self.logger.info(f"[PageProcessor] Processing page {page_num}")
                            page = pdfplumber_object.pages[page_num - 1]
                            
                            # 添加当前页面号到params
                            page_params = params.copy()
                            page_params['current_page_num'] = page_num
                            
                            # 3. 检测是否为扫描PDF
                            if self._is_scanned_pdf(pdfplumber_object, page_num):
                                # 记录警告日志
                                self.logger.warning(f"Detected scanned document (page {page_num}), automatically using Transformer extraction, user-specified method ignored")
                                # 转换为图像并使用Transformer
                                page_result = await self._process_page_as_scanned(page, page_params)
                            else:
                                # 4. 使用用户选择的方法
                                method = params.get('table_method', 'camelot')
                                flavor = params.get('table_flavor', 'auto')
                                
                                if flavor == 'auto':
                                    # 调用predict_table_type判断
                                    page_result = await self._process_with_auto_flavor(page, method, page_params)
                                else:
                                    # 直接使用指定方法和flavor
                                    page_result = await self._process_with_method(page, method, flavor, page_params)
                            
                            if page_result.get('success', True):
                                results['tables'].extend(page_result.get('tables', []))
                            else:
                                self.logger.error(f"[PageProcessor] Page {page_num} failed: {page_result.get('error', '')}")
                        except Exception as e:
                            self.logger.error(f"[PageProcessor] Page {page_num} processing failed: {str(e)}")
                            continue
            except Exception as e:
                self.logger.error(f"[PageProcessor] Failed to open PDF: {str(e)}")
                return {
                    'success': False,
                    'tables': [],
                    'export_path': None,
                    'pages': [],
                    'error': str(e)
                }

            # Save images if requested
            if params.get('save_images', False):
                try:
                    self.logger.info("[PageProcessor] Saving PDF images")
                    self._save_pdf_images(file_path, params)
                except Exception as e:
                    self.logger.error(f"[PageProcessor] Image saving failed: {str(e)}")

            # Export results if needed
            if params.get('export_results', True) and results['tables']:
                try:
                    self.logger.info("[PageProcessor] Exporting results")
                    export_path = self._handle_export(results, params)
                    results['export_path'] = export_path
                except Exception as e:
                    self.logger.error(f"[PageProcessor] Export failed: {str(e)}")
            self.logger.info("[PageProcessor] Processing finished")
            return {
                'success': True,
                'tables': results.get('tables', []),
                'export_path': results.get('export_path', None),
                'pages': page_list,
                'error': results.get('error', '')
            }
        except Exception as e:
            self.logger.error(f"[PageProcessor] Document processing failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'tables': [],
                'export_path': None,
                'pages': [],
                'error': str(e)
            }
 
    


    def _save_pdf_images(self, pdf_path: str, params: Dict[str, Any]) -> None:
        """Save images from PDF to output/images/filename/ folder
        
        Args:
            pdf_path: Path to the PDF file
            params: Processing parameters containing output_path
        """
        try:
            # Get output path and create images directory
            output_path = params.get('output_path', '')
            if not output_path:
                self.logger.error("Output path not specified for image saving")
                return
                
            # Create images directory structure: output/images/filename/
            pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]
            images_dir = os.path.join(output_path, 'images', pdf_filename)
            os.makedirs(images_dir, exist_ok=True)
            
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(pdf_path)
            image_index = 0
            
            # Process each page
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Get images from the page
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Get image data
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)
                        
                        # Skip if image is too small or invalid
                        if pix.width < 10 or pix.height < 10:
                            pix = None
                            continue
                            
                        # Convert to PIL Image
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = pix.tobytes("png")
                        else:  # CMYK: convert to RGB first
                            pix1 = fitz.Pixmap(fitz.csRGB, pix)
                            img_data = pix1.tobytes("png")
                            pix1 = None
                        
                        # Create PIL Image
                        pil_image = Image.open(io.BytesIO(img_data))
                        
                        # Try to get image name from PDF metadata
                        image_name = None
                        try:
                            # Check if image has a name in the PDF
                            if hasattr(img, 'name') and img.name:
                                image_name = img.name
                            # Alternative: check if there's a title or alt text
                            elif hasattr(img, 'title') and img.title:
                                image_name = img.title
                        except:
                            pass
                        
                        # Generate filename
                        if image_name:
                            # Clean the image name for filesystem
                            safe_name = "".join(c for c in image_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            safe_name = safe_name.replace(' ', '_')
                            if not safe_name:
                                safe_name = f"image_{image_index}"
                            filename = f"{safe_name}.png"
                        else:
                            # Use default naming: filename_page_index_image_index
                            filename = f"{pdf_filename}_page_{page_num + 1}_image_{img_index + 1}.png"
                        
                        # Save image
                        image_path = os.path.join(images_dir, filename)
                        pil_image.save(image_path, "PNG")
                        
                        self.logger.info(f"Saved image: {image_path}")
                        image_index += 1
                        
                        # Clean up
                        pix = None
                        
                    except Exception as e:
                        self.logger.error(f"Failed to save image {img_index} from page {page_num + 1}: {str(e)}")
                        continue
                        
            pdf_document.close()
            self.logger.info(f"Image saving completed. Images saved to: {images_dir}")
            
        except Exception as e:
            self.logger.error(f"Failed to save PDF images: {str(e)}", exc_info=True)

    



