import os
import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from SeedreamImageGenerator import SeedreamImageGenerator
from HailuoVideoGenerator import HailuoVideoGenerator
from comfyui import ComfyUIClient


class Shot:
    # 每个镜头的推荐时长
    DEFAULT_DURATION = 6
    SHORT_DURATION = 6
    LONG_DURATION = 10
    # 默认的保存路径
    DEFAULT_OUTPUT_DIR = "outputs"
    
    def __init__(self, 
                 hailuo_client:HailuoVideoGenerator, 
                 seedream_client:SeedreamImageGenerator, 
                 comfyui_client:ComfyUIClient,
                 shot_config: dict, 
                 output_dir: str = DEFAULT_OUTPUT_DIR
                ):
        """初始化分镜实例
        
        Args:
            hailuo_client: 海螺视频生成客户端
            seedream_client: Seedream图像生成客户端
            shot_config: 分镜配置字典
            output_dir: 输出目录路径
        """
        # 基础属性初始化
        self.id = shot_config["id"]
        self.lyric = shot_config.get("lyric", "")
        self.stable_prompt = shot_config.get("stable", "")
        self.dynamic_prompt = shot_config.get("dynamic", "")
        self.duration = shot_config.get("duration", self.DEFAULT_DURATION)
        self.sing = shot_config.get("sing", False)
        self.character_in_scene = shot_config.get("character", False)
        self.start_time = shot_config.get("startTime", "")
        self.end_time = shot_config.get("endTime", "")

        # 输出目录管理
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # API 客户端
        self.seedream = seedream_client
        self.hailuo = hailuo_client
        self.comfyui = comfyui_client

        # 中间结果路径
        self.character_reference_path: Optional[str] = None
        self.image_path: Optional[str] = None
        self.video_path: Optional[str] = None
        self.lip_sync_path: Optional[str] = None
        
    def _ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_timestamp(self) -> str:
        """生成时间戳标识"""
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")   
    
    def _construct_filename(self, prefix: str, extension: str) -> str:
        """构造文件名"""
        timestamp = self._generate_timestamp()
        return f"shot_{self.id}_{prefix}_{timestamp}.{extension}"    
    
    def generate_image(self, prompt: Optional[str] = None, filename: Optional[str] = None) -> str:
        """生成分镜图像
        
        Args:
            prompt: 生成提示词，如为None则使用配置中的stable prompt
            filename: 文件名，如为None则自动生成
            
        Returns:
            生成的图像文件路径
        """
        prompt = prompt or self.stable_prompt
        filename = filename or self._construct_filename("image", "png")
        save_path = str(self.output_dir / filename)

        try:
            url = self.seedream.generate_image(prompt=prompt, size="2K")
            self.seedream.save_image_from_url(url, save_path)
            self.image_path = save_path
            print(f"✅ Shot {self.id}: 图像已保存 {save_path}")
            return save_path
        except Exception as e:
            print(f"❌ Shot {self.id}: 图像生成失败 - {str(e)}")
            raise
    
    def edit_image(self, base_img_path: str, prompt: Optional[str] = None, filename: Optional[str] = None) -> str:
        """基于现有图像编辑生成新图像
        
        Args:
            base_img_path: 基础图像路径
            prompt: 编辑提示词
            filename: 文件名
            
        Returns:
            编辑后的图像路径
        """
        if not base_img_path or not os.path.exists(base_img_path):
            raise ValueError(f"基础图像路径无效: {base_img_path}")
            
        prompt = prompt or self.stable_prompt
        filename = filename or self._construct_filename("edited_image", "png")
        save_path = str(self.output_dir / filename)

        try:
            url = self.seedream.edit_image(base_image_path=base_img_path, prompt=prompt)
            self.seedream.save_image_from_url(url, save_path)
            self.image_path = save_path
            print(f"✅ Shot {self.id}: 图像编辑完成 {save_path}")
            return save_path
        except Exception as e:
            print(f"❌ Shot {self.id}: 图像编辑失败 - {str(e)}")
            raise

    def _determine_video_duration(self, duration: Optional[int] = None) -> int:
        """确定视频时长逻辑"""
        duration = duration or self.duration
        if duration <= self.SHORT_DURATION:
            return self.SHORT_DURATION
        else:
            return self.LONG_DURATION

    def generate_video(self, 
                      prompt: Optional[str] = None, 
                      filename: Optional[str] = None, 
                      use_image: bool = True, 
                      duration: Optional[int] = None) -> str:
        """生成分镜视频
        
        Args:
            prompt: 视频生成提示词
            filename: 输出文件名
            use_image: 是否使用已生成的图像作为基础
            duration: 视频时长
            
        Returns:
            生成的视频文件路径
        """
        final_duration = self._determine_video_duration(duration)
        filename = filename or self._construct_filename("video", "mp4")
        save_path = str(self.output_dir / filename)
        
        try:
            if use_image and self.image_path:
                prompt = prompt or self.dynamic_prompt
                task_id = self.hailuo.invoke_image_to_video(prompt, self.image_path, duration=final_duration)
            else:
                prompt = prompt or f"{self.stable_prompt}, {self.dynamic_prompt}"
                task_id = self.hailuo.invoke_text_to_video(prompt, duration=final_duration)

            file_id = self.hailuo.query_task_status(task_id)
            self.hailuo.fetch_video(file_id, save_path)
            self.video_path = save_path
            print(f"✅ Shot {self.id}: 视频已保存 {save_path}")
            return save_path
        except Exception as e:
            print(f"❌ Shot {self.id}: 视频生成失败 - {str(e)}")
            raise
        
    def video_lip_sync(self,
                       audio_path:str,
                       file_name: Optional[str] = None,
                       startTime: Optional[str] = None,
                       endTime: Optional[str] = None,
                       prompt: Optional[str] = None,
                       ):
        """使用ComfyUI工作流对口型"""
        if not self.video_path:
            raise ValueError("本shot没有要对口型的视频!")
        input_files = {
            "video": self.video_path,
            "audio": audio_path,
        }
        if not startTime:
            startTime = self.start_time
        if not endTime:
            endTime = self.end_time
        params = {
            "time": {
                "start_time": startTime,
                "end_time": endTime
            }
        }
        if prompt:
            params["prompt"] = {"positive":prompt}
        if not file_name:
            file_name = self._construct_filename("lipSync", "mp4")
        workflow = self.comfyui.load_workflow(None)
        saved_paths = self.comfyui.execute_workflow(workflow_json=workflow, input_files=input_files, params=params, output_dir=self.output_dir, file_name=file_name)
        self.lip_sync_path = str(saved_paths[-1])
        return saved_paths
    