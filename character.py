import datetime
from pathlib import Path
from SeedreamImageGenerator import SeedreamImageGenerator 

class CharacterReference:
    def __init__(self, seedream_client: SeedreamImageGenerator, character_config: str, output_dir: str = "outputs"):
        self.description = character_config
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # API 客户端
        self.seedream = seedream_client

        # 中间结果
        self.image_path = None

    def generate_image(self, prompt: str = None, filename: str = None):
        """生成角色参考图"""
        prompt = prompt or self.description
        # 以时间作为唯一标识
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filename or f"character_reference_{timestamp}.png"
        save_path = str(self.output_dir / filename)

        url = self.seedream.generate_image(prompt=prompt, size="2K")
        self.seedream.save_image_from_url(url, save_path)
        self.image_path = save_path
        print(f"✅ 角色参考图已保存 {save_path}")
        return save_path
