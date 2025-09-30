import os
import time
import base64
import requests
import mimetypes
from pathlib import Path


class HailuoVideoGenerator:
    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/v1", output_dir: str = "output"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.cur_dir = Path(__file__).parent
        self.output_dir = Path(output_dir)
        if not self.output_dir.is_absolute():
            self.output_dir = self.cur_dir / self.output_dir

        # 创建目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def image_to_data_url(image_path: str) -> str:
        """本地图片转 base64 Data URL"""
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None:
            mime_type = "application/octet-stream"
        with open(image_path, "rb") as f:
            base64_str = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{base64_str}"

    def invoke_text_to_video(self, prompt: str, model: str = "MiniMax-Hailuo-02",
                             duration: int = 6, resolution: str = "768P") -> str:
        """通过文本发起视频生成任务，返回 task_id"""
        url = f"{self.base_url}/video_generation"
        payload = {
            "prompt": prompt,
            "model": model,
            "duration": duration,
            "resolution": resolution,
        }
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()["task_id"]

    def invoke_image_to_video(self, prompt: str, image_path: str,
                              model: str = "MiniMax-Hailuo-02",
                              duration: int = 6, resolution: str = "768P") -> str:
        """通过本地首帧图像+文本描述发起视频生成任务，返回 task_id"""
        url = f"{self.base_url}/video_generation"
        img_base64 = self.image_to_data_url(image_path)
        payload = {
            "prompt": prompt,
            "first_frame_image": img_base64,
            "model": model,
            "duration": duration,
            "resolution": resolution,
        }
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()["task_id"]

    def query_task_status(self, task_id: str, poll_interval: int = 10) -> str:
        """轮询任务状态直到成功或失败，返回 file_id"""
        url = f"{self.base_url}/query/video_generation"
        params = {"task_id": task_id}
        while True:
            time.sleep(poll_interval)
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            status = data["status"]
            print(f"任务 {task_id} 当前状态: {status}")
            if status == "Success":
                return data["file_id"]
            elif status == "Fail":
                raise RuntimeError(f"视频生成失败: {data.get('error_message', '未知错误')}")

    def fetch_video(self, file_id: str, save_path: str) -> Path:
        """根据 file_id 获取下载链接并保存视频，返回文件路径"""
        url = f"{self.base_url}/files/retrieve"
        params = {"file_id": file_id}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        download_url = response.json()["file"]["download_url"]

        video_response = requests.get(download_url)
        video_response.raise_for_status()

        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(video_response.content)

        print(f"✅ 视频已保存至 {save_path}")
        return save_path



# 示例 main.py 集成用法
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("MINIMAX_API_KEY")
    generator = HailuoVideoGenerator(api_key=API_KEY)
    prompt = "男人对着镜头甜甜地微笑, 随即转身"
    image_path = r"output\character_reference_20250928_022354.png"
    task_id = generator.invoke_image_to_video(prompt, image_path)
    


    file_id = generator.query_task_status(task_id)
    generator.fetch_video(file_id=file_id, save_path="output/test.mp4")  # 🔥 直接传完整路径