/**
 * Unified Layout Annotation System
 * 统一的版面标注系统，用于显示和交互版面分析结果
 */

class LayoutAnnotator {
    constructor(canvasId, imageId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('[LayoutAnnotator] Canvas element not found:', canvasId);
            this.ctx = null;
            this.image = document.getElementById(imageId);
            this.config = { ...options };
            this.elements = [];
            return;
        }
        this.ctx = this.canvas.getContext && this.canvas.getContext('2d');
        if (!this.ctx) {
            console.error('[LayoutAnnotator] Failed to get 2D context for canvas:', canvasId);
        }
        this.image = document.getElementById(imageId);

        // 配置
        this.config = {
            drawBbox: true,              // 绘制边界框
            drawPolygon: false,           // 绘制多边形（用于旋转）
            showLabels: true,             // 显示标签
            showConfidence: true,         // 显示置信度
            highlightHover: true,         // 鼠标悬停高亮
            enableInteraction: true,      // 启用交互
            labelOffset: 10,              // 标签偏移
            borderWidth: 2,               // 边框宽度
            ...options
        };

        // 状态
        this.elements = [];              // 所有版面元素
        this.hoveredElement = null;      // 当前悬停元素
        this.selectedElement = null;     // 当前选中元素
        this.filteredTypes = new Set();  // 过滤的元素类型
        this.elementColors = {};         // 元素类型颜色映射

        // 绑定事件处理器
        this.setupEventListeners();

        // 当图片加载完成时（或已加载），调整 canvas 尺寸以匹配图片
        if (this.image) {
            this.image.addEventListener('load', () => {
                this.resizeCanvasToImage();
            });
            if (this.image.complete) {
                // 已加载的图片立即调整
                this.resizeCanvasToImage();
            }
        }
    }

    /**
     * 加载和显示版面分析结果
     */
    loadLayoutAnalysis(layoutResult) {
        if (!layoutResult || !layoutResult.elements) {
            console.warn('Invalid layout result structure');
            return;
        }

        this.elements = layoutResult.elements;

        // 构建颜色映射
        this.elementColors = {};
        layoutResult.elements.forEach(elem => {
            if (!this.elementColors[elem.element_type]) {
                this.elementColors[elem.element_type] = this.getTypeColor(elem.element_type);
            }
        });

        // 重新绘制
        this.redraw();
    }

    /**
     * 获取元素类型的颜色
     */
    getTypeColor(elementType) {
        const colorMap = {
            'text': '#4A90E2',              // 蓝色
            'title': '#F5A623',             // 橙色
            'subtitle': '#BD10E0',          // 紫色
            'section_header': '#7ED321',    // 绿色
            'table': '#FF6B6B',             // 红色
            'table_header': '#FF4757',      // 深红
            'figure': '#2E86C1',            // 深蓝
            'image': '#16A085',             // 青色
            'page_header': '#C0392B',       // 棕红
            'page_footer': '#8E44AD',       // 深紫
            'footnote': '#95A5A6',          // 灰色
            'formula': '#E67E22',           // 棕色
            'list_item': '#3498DB'          // 浅蓝
        };
        return colorMap[elementType] || '#808080';
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        if (!this.config.enableInteraction) {
            return;
        }
        if (!this.canvas) return;
        if (!this.canvas.addEventListener) return;

        // Ensure canvas can receive pointer events
        try {
            this.canvas.style.pointerEvents = 'auto';
        } catch (e) {}

        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseleave', (e) => this.handleMouseLeave(e));
        this.canvas.addEventListener('click', (e) => this.handleClick(e));
    }

    /**
     * 处理鼠标移动 - 高亮悬停元素
     */
    handleMouseMove(e) {
        if (!this.config.highlightHover) return;

        const rect = this.canvas.getBoundingClientRect();
        // Map client coordinates to canvas internal coordinates (which use image natural pixels)
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        const element = this.getElementAtPoint(x, y);

        if (element !== this.hoveredElement) {
            this.hoveredElement = element;
            this.canvas.style.cursor = element ? 'pointer' : 'default';
            this.redraw();
        }
    }

    /**
     * 处理鼠标离开
     */
    handleMouseLeave(e) {
        if (this.hoveredElement) {
            this.hoveredElement = null;
            this.redraw();
        }
    }

    /**
     * 处理点击 - 选中元素
     */
    handleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        const element = this.getElementAtPoint(x, y);
        this.selectedElement = element;

        if (element) {
            this.showElementDetails(element);
            this.dispatchElementSelected(element);
        }

        this.redraw();
    }

    /**
     * 获取指定点所在的元素
     */
    getElementAtPoint(x, y) {
        // 从上层元素开始检查（z_index高的优先）
        for (let i = this.elements.length - 1; i >= 0; i--) {
            const elem = this.elements[i];
            if (this.filteredTypes.has(elem.element_type)) {
                continue; // 跳过被过滤的类型
            }

            const bbox = elem.bbox;
            if (x >= bbox[0] && x <= bbox[2] && y >= bbox[1] && y <= bbox[3]) {
                return elem;
            }
        }
        return null;
    }

    /**
     * 重绘Canvas
     */
    redraw() {
        if (!this.canvas || !this.ctx) return;

        // 清空canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // 绘制背景（如果有图像）
        if (this.image && this.image.complete) {
            this.ctx.drawImage(this.image, 0, 0, this.canvas.width, this.canvas.height);
        }

        // 绘制所有元素
        this.elements.forEach(elem => {
            // 跳过被过滤的类型
            if (this.filteredTypes.has(elem.element_type)) {
                return;
            }

            const isHovered = this.hoveredElement === elem;
            const isSelected = this.selectedElement === elem;

            this.drawElement(elem, isHovered, isSelected);
        });
    }

    /**
     * 绘制单个元素
     */
    drawElement(elem, isHovered = false, isSelected = false) {
        const color = this.elementColors[elem.element_type];
        const bbox = elem.bbox;

        // 确定线条样式
        let lineWidth = this.config.borderWidth;
        let alpha = 0.3;

        if (isSelected) {
            lineWidth = 4;
            alpha = 0.6;
        } else if (isHovered) {
            lineWidth = 3;
            alpha = 0.5;
        }

        // 绘制边界框
        if (this.config.drawBbox) {
            this.drawBbox(bbox, color, lineWidth, alpha, isSelected);
        }

        // 绘制多边形（如果有旋转）
        if (this.config.drawPolygon && elem.polygon) {
            this.drawPolygon(elem.polygon, color, lineWidth, alpha);
        }

        // 绘制标签
        if (this.config.showLabels) {
            this.drawLabel(elem, bbox, color, isSelected);
        }
    }

    /**
     * 绘制边界框
     */
    drawBbox(bbox, color, lineWidth, alpha, isSelected = false) {
        const [x1, y1, x2, y2] = bbox;
        const width = x2 - x1;
        const height = y2 - y1;

        // 填充
        this.ctx.fillStyle = this.hexToRgba(color, alpha);
        this.ctx.fillRect(x1, y1, width, height);

        // 边框
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = lineWidth;
        this.ctx.strokeRect(x1, y1, width, height);

        // 如果选中，绘制角标
        if (isSelected) {
            this.drawCornerMarkers(bbox);
        }
    }

    /**
     * 绘制多边形（用于旋转元素）
     */
    drawPolygon(polygon, color, lineWidth, alpha) {
        if (!polygon || polygon.length < 8) return;

        // 将扁平数组转换为坐标对 [[x,y], [x,y], ...]
        const points = [];
        for (let i = 0; i < polygon.length; i += 2) {
            points.push([polygon[i], polygon[i + 1]]);
        }

        // 填充
        this.ctx.fillStyle = this.hexToRgba(color, alpha);
        this.ctx.beginPath();
        this.ctx.moveTo(points[0][0], points[0][1]);
        points.slice(1).forEach(p => this.ctx.lineTo(p[0], p[1]));
        this.ctx.closePath();
        this.ctx.fill();

        // 边框
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = lineWidth;
        this.ctx.stroke();
    }

    /**
     * 绘制角标（用于选中状态）
     */
    drawCornerMarkers(bbox) {
        const [x1, y1, x2, y2] = bbox;
        const size = 8;

        const corners = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]];

        this.ctx.fillStyle = '#FF6B6B';
        corners.forEach(([x, y]) => {
            this.ctx.fillRect(x - size/2, y - size/2, size, size);
        });
    }

    /**
     * 绘制标签
     */
    drawLabel(elem, bbox, color, isSelected = false) {
        const [x1, y1, x2, y2] = bbox;

        // 标签文本
        let label = this.getElementLabel(elem);
        if (this.config.showConfidence && elem.confidence) {
            label += ` (${(elem.confidence * 100).toFixed(0)}%)`;
        }

        // 标签背景
        const padding = 4;
        const fontSize = isSelected ? 14 : 12;

        this.ctx.font = `bold ${fontSize}px Arial`;
        const metrics = this.ctx.measureText(label);
        const labelWidth = metrics.width + padding * 2;
        const labelHeight = fontSize + padding * 2;

        // 标签位置：在元素左上角下方
        const labelX = x1;
        const labelY = y1 + this.config.labelOffset;

        // 背景
        this.ctx.fillStyle = color;
        this.ctx.globalAlpha = 0.9;
        this.ctx.fillRect(labelX, labelY, labelWidth, labelHeight);

        // 文字
        this.ctx.globalAlpha = 1;
        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.textBaseline = 'top';
        this.ctx.fillText(label, labelX + padding, labelY + padding);
    }

    /**
     * 获取元素的显示标签
     */
    getElementLabel(elem) {
        let label = elem.element_type.toUpperCase();

        // 特殊标签
        if (elem.element_type === 'table' && elem.table_rows && elem.table_cols) {
            label = `TABLE ${elem.table_rows}×${elem.table_cols}`;
        }

        // 限制长度
        if (elem.content && elem.content.length > 0) {
            const content = elem.content.substring(0, 20);
            label += `: ${content}...`;
        }

        return label;
    }

    /**
     * 显示元素详情
     */
    showElementDetails(elem) {
        const details = {
            type: elem.element_type,
            bbox: elem.bbox,
            confidence: elem.confidence,
            content: elem.content,
            area: elem.area,
            width: elem.width,
            height: elem.height
        };

        if (elem.table_rows && elem.table_cols) {
            details.table_size = `${elem.table_rows} × ${elem.table_cols}`;
        }

        console.log('Selected Element:', details);
    }

    /**
     * 按类型过滤元素显示
     */
    filterByType(elementType, visible = false) {
        if (visible) {
            this.filteredTypes.delete(elementType);
        } else {
            this.filteredTypes.add(elementType);
        }
        this.redraw();
    }

    /**
     * 设置所有类型的可见性
     */
    setAllTypesVisible(visible = true) {
        if (visible) {
            this.filteredTypes.clear();
        } else {
            // 隐藏所有
            this.elements.forEach(elem => {
                this.filteredTypes.add(elem.element_type);
            });
        }
        this.redraw();
    }

    /**
     * 获取可见的元素
     */
    getVisibleElements() {
        return this.elements.filter(elem => !this.filteredTypes.has(elem.element_type));
    }

    /**
     * 调整canvas大小以匹配图像
     */
    resizeCanvasToImage() {
        if (!this.image) return;

        // Displayed size in CSS pixels
        const displayedWidth = this.image.offsetWidth || this.image.clientWidth || this.image.naturalWidth;
        const displayedHeight = this.image.offsetHeight || this.image.clientHeight || this.image.naturalHeight;

        // Ensure the image's immediate parent is positioned so absolute canvas can overlay
        try {
            const parent = this.canvas.parentElement;
            if (parent && getComputedStyle(parent).position === 'static') {
                parent.style.position = 'relative';
            }
        } catch (e) {}

        // Set CSS size so canvas overlays visually match the image on screen
        this.canvas.style.width = `${displayedWidth}px`;
        this.canvas.style.height = `${displayedHeight}px`;

        // Set internal pixel buffer to the image natural size (so element bboxes in natural image coords map 1:1)
        this.canvas.width = this.image.naturalWidth || displayedWidth;
        this.canvas.height = this.image.naturalHeight || displayedHeight;

        // Ensure canvas is visible and on top
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.zIndex = '1000';

        // Redraw with updated sizes
        this.redraw();
    }

    /**
     * 导出当前标注
     */
    exportAnnotations() {
        return {
            timestamp: new Date().toISOString(),
            imageSize: {
                width: this.canvas.width,
                height: this.canvas.height
            },
            elements: this.getVisibleElements(),
            selectedElement: this.selectedElement
        };
    }

    /**
     * 辅助方法：十六进制转RGBA
     */
    hexToRgba(hex, alpha = 1) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    /**
     * 分发元素选中事件
     */
    dispatchElementSelected(elem) {
        const event = new CustomEvent('elementSelected', {
            detail: elem
        });
        this.canvas.dispatchEvent(event);
    }
}


/**
 * Layout Control Panel
 * 版面标注控制面板
 */
class LayoutControlPanel {
    constructor(panelId, annotator) {
        this.panel = document.getElementById(panelId);
        this.annotator = annotator;
        this.elementTypes = new Set();
        this.init();
    }

    init() {
        // 从annotator的元素中收集所有类型
        this.annotator.elements.forEach(elem => {
            this.elementTypes.add(elem.element_type);
        });

        this.createControlUI();
    }

    createControlUI() {
        // 清空面板
        this.panel.innerHTML = '';

        // 统计信息
        const stats = document.createElement('div');
        stats.style.cssText = 'margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 4px;';

        const totalElems = this.annotator.getVisibleElements().length;
        stats.innerHTML = `<strong>Total Elements:</strong> ${totalElems}`;
        this.panel.appendChild(stats);

        // 类型过滤器
        const filterSection = document.createElement('div');
        const filterTitle = document.createElement('h4');
        filterTitle.textContent = 'Filter by Type';
        filterTitle.style.marginTop = '0';
        filterSection.appendChild(filterTitle);

        // 全选/全不选按钮
        const buttonContainer = document.createElement('div');
        buttonContainer.style.marginBottom = '10px';

        const showAllBtn = document.createElement('button');
        showAllBtn.textContent = 'Show All';
        showAllBtn.style.cssText = 'margin-right: 5px; padding: 5px 10px; background: #4A90E2; color: white; border: none; border-radius: 4px; cursor: pointer;';
        showAllBtn.onclick = () => this.annotator.setAllTypesVisible(true);
        buttonContainer.appendChild(showAllBtn);

        const hideAllBtn = document.createElement('button');
        hideAllBtn.textContent = 'Hide All';
        hideAllBtn.style.cssText = 'padding: 5px 10px; background: #808080; color: white; border: none; border-radius: 4px; cursor: pointer;';
        hideAllBtn.onclick = () => this.annotator.setAllTypesVisible(false);
        buttonContainer.appendChild(hideAllBtn);

        filterSection.appendChild(buttonContainer);

        // 类型复选框
        const typeList = document.createElement('div');
        typeList.style.cssText = 'display: flex; flex-direction: column; gap: 8px;';

        Array.from(this.elementTypes).sort().forEach(type => {
            const label = document.createElement('label');
            label.style.cssText = 'display: flex; align-items: center; gap: 8px; cursor: pointer;';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = true;
            checkbox.onchange = (e) => {
                this.annotator.filterByType(type, e.target.checked);
            };

            const color = document.createElement('span');
            color.style.cssText = `width: 16px; height: 16px; background: ${this.annotator.getTypeColor(type)}; border-radius: 2px;`;

            const typeLabel = document.createElement('span');
            typeLabel.textContent = type.charAt(0).toUpperCase() + type.slice(1);

            label.appendChild(checkbox);
            label.appendChild(color);
            label.appendChild(typeLabel);
            typeList.appendChild(label);
        });

        filterSection.appendChild(typeList);
        this.panel.appendChild(filterSection);
    }
}
