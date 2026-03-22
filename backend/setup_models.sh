#!/bin/bash
# spaCy 模型安装脚本（Linux/Mac）

echo "=========================================="
echo "DocuVision - spaCy 模型安装脚本"
echo "=========================================="
echo ""

# 检查 spacy 是否已安装
echo "步骤 1: 检查 spacy 包..."
python -c "import spacy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ spacy 未安装，正在安装..."
    pip install spacy==3.7.2
    if [ $? -ne 0 ]; then
        echo "❌ spacy 安装失败，请检查网络连接和 pip 配置"
        exit 1
    fi
    echo "✅ spacy 安装成功"
else
    echo "✅ spacy 已安装"
fi

echo ""
echo "步骤 2: 下载 spaCy 语言模型..."
echo ""

# 下载英文模型
echo "正在下载英文模型 (en_core_web_sm)..."
python -m spacy download en_core_web_sm
if [ $? -eq 0 ]; then
    echo "✅ 英文模型下载成功"
else
    echo "❌ 英文模型下载失败"
    exit 1
fi

echo ""
echo "是否下载中文模型？(y/n)"
read -r answer
if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    echo "正在下载中文模型 (zh_core_web_sm)..."
    python -m spacy download zh_core_web_sm
    if [ $? -eq 0 ]; then
        echo "✅ 中文模型下载成功"
    else
        echo "⚠️  中文模型下载失败（可选，不影响主要功能）"
    fi
fi

echo ""
echo "步骤 3: 验证安装..."
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('✅ spaCy 模型验证成功')"

echo ""
echo "=========================================="
echo "✅ 安装完成！"
echo "=========================================="

