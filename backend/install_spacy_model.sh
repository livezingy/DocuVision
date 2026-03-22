#!/bin/bash
# spaCy 模型安装脚本 - 多方案尝试（Linux/Mac）

echo "=========================================="
echo "DocuVision - spaCy 模型安装（多方案）"
echo "=========================================="
echo ""

# 检查 spacy 是否已安装
echo "[1/5] 检查 spacy 包..."
python -c "import spacy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ spacy 未安装，正在安装..."
    pip install spacy==3.7.2
    if [ $? -ne 0 ]; then
        echo "❌ spacy 安装失败"
        exit 1
    fi
    echo "✅ spacy 安装成功"
else
    echo "✅ spacy 已安装"
fi

echo ""
echo "[2/5] 尝试方法 1: 使用 pip 直接安装 wheel 文件..."
echo "这是最稳定的方法，推荐使用"
echo ""

pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

if [ $? -eq 0 ]; then
    echo "✅ 方法 1 成功！"
    goto_verify=true
else
    echo ""
    echo "[3/5] 方法 1 失败，尝试方法 2: 使用国内镜像源..."
    echo ""
    
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple spacy
    python -m spacy download en_core_web_sm
    
    if [ $? -eq 0 ]; then
        echo "✅ 方法 2 成功！"
        goto_verify=true
    else
        echo ""
        echo "[4/5] 方法 2 失败，尝试方法 3: 标准下载命令..."
        echo ""
        
        python -m spacy download en_core_web_sm
        
        if [ $? -eq 0 ]; then
            echo "✅ 方法 3 成功！"
            goto_verify=true
        else
            echo ""
            echo "[5/5] 所有自动方法都失败"
            echo ""
            echo "⚠️  请尝试手动安装："
            echo ""
            echo "1. 访问: https://github.com/explosion/spacy-models/releases"
            echo "2. 下载: en_core_web_sm-3.7.1-py3-none-any.whl"
            echo "3. 运行: pip install ~/Downloads/en_core_web_sm-3.7.1-py3-none-any.whl"
            echo ""
            echo "或者使用 SimpleNLP（系统会自动降级，功能有限但可用）"
            echo ""
            exit 1
        fi
    fi
fi

if [ "$goto_verify" = true ]; then
    echo ""
    echo "=========================================="
    echo "验证安装..."
    echo "=========================================="
    python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('✅ spaCy 模型验证成功！')"
    
    if [ $? -ne 0 ]; then
        echo "❌ 验证失败，模型可能未正确安装"
        exit 1
    fi
    
    echo ""
    echo "=========================================="
    echo "✅ 安装完成！"
    echo "=========================================="
    echo ""
    read -p "是否安装中文模型？(y/n): " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        echo ""
        echo "正在安装中文模型..."
        pip install https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.7.0/zh_core_web_sm-3.7.0-py3-none-any.whl
        if [ $? -eq 0 ]; then
            echo "✅ 中文模型安装成功"
        else
            echo "⚠️  中文模型安装失败（可选，不影响主要功能）"
        fi
    fi
fi

echo ""

