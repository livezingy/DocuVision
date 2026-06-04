import os
import json
import yaml
import re
from pathlib import Path
from PIL import Image

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

    def get_prompt(self, type_id, query_fields=None, merged_schema=None):
        """Build final prompt; optional query_fields extend schema (validated upstream)."""
        config = self._load_config(type_id)
        if merged_schema is not None:
            schema = merged_schema
        elif query_fields:
            from app.services.kie.query_fields import build_merged_schema

            schema = build_merged_schema(config["schema"], query_fields)
        else:
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
        """从模型输出中提取 JSON 对象（容忍 Markdown 围栏与常见格式噪声）。"""
        if not text or not str(text).strip():
            return None

        candidates: list[str] = []

        def _push(s: str) -> None:
            s = (s or "").strip()
            if s and s not in candidates:
                candidates.append(s)

        raw = str(text).strip().lstrip("\ufeff")
        _push(raw)

        for pattern in (
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
        ):
            for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
                _push(match.group(1))

        brace = re.search(r"\{[\s\S]*\}", raw)
        if brace:
            _push(brace.group(0))

        for candidate in candidates:
            for attempt in (candidate, self._sanitize_json_text(candidate)):
                if not attempt:
                    continue
                try:
                    parsed = json.loads(attempt)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def _sanitize_json_text(text: str) -> str:
        """去掉尾随逗号等常见模型输出噪声。"""
        t = text.strip()
        t = re.sub(r",\s*}", "}", t)
        t = re.sub(r",\s*]", "]", t)
        return t

    def extract(self, image_path, option_type, lang=None, query_fields=None, merged_schema=None):
        """
        Extract fields for option_type using optional runtime query field extensions.
        Returns dict with "type" and "fields".
        """
        actual_type = option_type

        prompt = self.get_prompt(
            actual_type,
            query_fields=query_fields,
            merged_schema=merged_schema,
        )
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
