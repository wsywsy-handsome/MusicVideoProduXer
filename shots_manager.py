import json
import os
from pathlib import Path
from shot import Shot
from character import CharacterReference
from SeedreamImageGenerator import SeedreamImageGenerator
from HailuoVideoGenerator import HailuoVideoGenerator
from comfyui import ComfyUIClient
from dotenv import load_dotenv


class ShotsManager:
    def __init__(self, json_path: str, output_dir: str = "output_final"):
        """管理一场 MV 的所有 Shot"""
        self.json_path = Path(json_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reference_pic_dir = None
        # 加载环境变量
        load_dotenv()
        self.hailuo_api_key = os.getenv("MINIMAX_API_KEY") 
        self.seedream_api_key = os.getenv("ARK_API_KEY")
        
        # 初始化全局API客户端
        self.seedream = SeedreamImageGenerator(
            api_key=self.seedream_api_key,
            output_dir=self.output_dir
        )
        self.hailuo = HailuoVideoGenerator(
            api_key=self.hailuo_api_key,
            output_dir=self.output_dir
        )
        self.comfyui = ComfyUIClient(
            server_address="localhost:8190", 
            save_dir=self.output_dir
        )
        
        # 初始化shots和Character
        self.shots, self.character_description = self._load_shots()
        # 初始化一个字典用来存放所有提示词
        self.prompts = {}
        for i, shot in enumerate(self.shots):
            if shot.character_in_scene:
                self.prompts[i] = {"pic":shot.stable_prompt, "vid":shot.dynamic_prompt}
            else:
                self.prompts[i] = {"pic":None, "vid":f"{shot.stable_prompt}, {shot.dynamic_prompt}"}
        
                
    def _load_shots(self):
        """从 JSON 文件读取配置并实例化所有 Shot"""
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        character_description = CharacterReference(
            seedream_client=self.seedream,
            character_config=data["character_description"],
            output_dir=self.output_dir)
        shots = []
        for shot_config in data["shots"]:
            shot = Shot(
                hailuo_client=self.hailuo,
                seedream_client=self.seedream,
                comfyui_client=self.comfyui,
                shot_config=shot_config,
                output_dir=self.output_dir
            )
            shots.append(shot)
        return shots, character_description

    def list_shots(self):
        """打印所有 shot 的基本信息"""
        print("character:", self.character_description.description)
        for shot in self.shots:
            print(f"Shot {shot.id}: {shot.lyric} (Duration: {shot.duration}s, Sing: {shot.sing})")

    def get_shot_by_id(self, shot_id: int) -> Shot:
        """根据 ID 获取某个 Shot"""
        for shot in self.shots:
            if shot.id == shot_id:
                return shot
        raise ValueError(f"Shot {shot_id} not found")
    
    def generate_reference(self):
        """根据character_description生成角色参考照"""
        self.reference_pic_dir = self.character_description.generate_image()
        return self.reference_pic_dir
    
    def generate_first_frame(self, shot_index, reference_dir: str = None, prompt: str = None):
        """修改角色参考图以生成第一帧图像"""
        shot = self.shots[shot_index]
        if reference_dir:
            return shot.edit_image(base_img_path=reference_dir, prompt=prompt)
        else:
            return shot.edit_image(base_img_path=self.reference_pic_dir, prompt=prompt)

if __name__ == "__main__":
    manager = ShotsManager(
        "/root/shared-nvme/shuyiwang/MusicVideo_ProduXer/shots.json",
        "./outputttt",
    )
    shot = manager.shots[1]
    shot.video_path="/root/shared-nvme/shuyiwang/MusicVideo_ProduXer/output_final/shot_7_video_20251001_021412.mp4"
    shot.video_lip_sync(audio_path="/root/shared-nvme/shuyiwang/MusicVideo_ProduXer/我不明白.mp3")