import os
import json
import yaml
import re
from pathlib import Path
from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

_DEFAULT_KIE_CONFIG_DIR = Path(__file__).resolve().parent / "kie_configs"


class KieManager:
    def __init__(self, model, processor, config_dir=None):
        """
        model: Qwen2_5_VLForConditionalGeneration 实例
        processor: AutoProcessor 实例
        config_dir: 存放 YAML 配置的文件夹路径（默认与包内 kie_configs 同级）
        """
        self.model = model
        self.processor = processor
        self.config_dir = Path(config_dir) if config_dir is not None else _DEFAULT_KIE_CONFIG_DIR
        self._cache = {}
        # 加载注册表
        with open(self.config_dir / "_registry.yaml", "r", encoding="utf-8") as f:
            self.registry = yaml.safe_load(f)

    def _load_config(self, type_id):
        if type_id not in self._cache:
            file_path = self.config_dir / f"{type_id}.yaml"
            with open(file_path, "r", encoding="utf-8") as f:
                self._cache[type_id] = yaml.safe_load(f)
        return self._cache[type_id]

    def get_type_list(self):
        """返回所有文档类型信息，供 UI 展示"""
        type_list = []
        for type_id in self.registry["types"]:
            config = self._load_config(type_id)
            type_list.append({
                "id": type_id,
                "name": config["display_name"],
                "category": config.get("category", "document")
            })
        return type_list

    def get_prompt(self, type_id):
        """根据类型 id 生成最终的 prompt 字符串"""
        config = self._load_config(type_id)
        schema = config["schema"]
        schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
        prompt = config["prompt_template"].replace("{{ schema_json }}", schema_json)
        return prompt

    def _qwen_generate(self, messages, max_new_tokens=2048):
        """封装 Qwen2.5-VL 的推理，返回生成的文本"""
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs = []
        # 提取所有图片
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for item in msg["content"]:
                    if item.get("type") == "image":
                        img = Image.open(item["image"]).convert("RGB")
                        image_inputs.append(img)
        if not image_inputs:
            image_inputs = None
        inputs = self.processor(
            text=[text],
            images=image_inputs if image_inputs else None,
            padding=True,
            return_tensors="pt"
        ).to(self.model.device)
        generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
        generated_text = self.processor.batch_decode(
            generated_ids[:, inputs.input_ids.shape[1]:], skip_special_tokens=True
        )[0]
        return generated_text

    def _parse_json(self, text):
        """从模型输出中提取 JSON 对象"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 提取 ```json ... ``` 代码块
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试提取 {} 包裹的部分
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def extract(self, image_path, option_type, lang=None):
        """
        根据选项类型进行提取。
        option_type: 如 "invoice", "receipt", "id_card", "passport", "bank_card"
        lang: 预留参数，当前未使用（所有 prompt 为中文）
        返回: dict，包含 "type" 字段与 "fields" 字段（提取结果）
        """
        actual_type = option_type

        # 生成 prompt 并提取
        prompt = self.get_prompt(actual_type)
        messages = [
            {"role": "user", "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": prompt}
            ]}
        ]
        raw_text = self._qwen_generate(messages, max_new_tokens=2048)
        fields = self._parse_json(raw_text)
        return {
            "type": actual_type,
            "fields": fields if fields else {"raw_output": raw_text}
        }
