import base64
import requests
from pathlib import Path
from volcenginesdkarkruntime import Ark


class SeedreamImageGenerator:
    def __init__(self, api_key: str, base_url: str = "https://ark.cn-beijing.volces.com/api/v3", output_dir: str = "output"):
        self.client = Ark(base_url=base_url, api_key=api_key)
        self.cur_dir = Path(__file__).parent
        self.output_dir = Path(output_dir)
        if not self.output_dir.is_absolute():
            self.output_dir = self.cur_dir / self.output_dir

        # 创建目录
        self.output_dir.mkdir(parents=True, exist_ok=True)


    def generate_image(self, prompt: str, model: str = "doubao-seedream-4-0-250828",
                       size: str = "2K", watermark: bool = False) -> str:
        """根据文本 prompt 生成图片，返回图片 URL"""
        resp = self.client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            response_format="url",
            watermark=watermark
        )
        return resp.data[0].url

    def save_image_from_url(self, url: str, filename: str):
        """下载并保存图片"""
        resp = requests.get(url)
        resp.raise_for_status()
        filepath = self.cur_dir / filename
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath

    @staticmethod
    def image_to_base64(filepath: Path) -> str:
        with open(filepath, "rb") as f:
            img_bytes = f.read()
        return f"data:image/png;base64,{base64.b64encode(img_bytes).decode('utf-8')}"

    def edit_image(self, base_image_path: Path, prompt: str,
                model: str = "doubao-seedream-4-0-250828",
                size: str = "2560x1440", watermark: bool = False) -> str:
        """基于已有图片 + prompt 生成新图，返回图片 URL"""
        img_data_uri = self.image_to_base64(base_image_path)
        resp = self.client.images.generate(
            model=model,
            prompt=prompt,
            image=img_data_uri,
            size=size,
            response_format="url",
            watermark=watermark
        )
        return resp.data[0].url

# 示例 main.py 集成用法
if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    load_dotenv()
    API_KEY = os.getenv("ARK_API_KEY")  # 建议放到环境变量里

    generator = SeedreamImageGenerator(api_key=API_KEY)

    # Step 1: 生成基础人物图
    prompt = "一个美丽青春的高中生"
    url = generator.generate_image(prompt)
    # print(f"基础人物图 URL: {url}")
    person_path = generator.save_image_from_url(url, "person.png")

    # Step 2: 基于基础人物图做变体
    new_prompt = "给人物添加一件红色铠甲"
    url2 = generator.edit_image(person_path, new_prompt)
    edited_path = generator.save_image_from_url(url2, "output.png")
