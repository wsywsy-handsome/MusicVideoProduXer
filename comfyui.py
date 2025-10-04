import json
import requests
import websockets
import asyncio
import threading
import uuid
import os
from typing import Dict, Any, Optional, List

class ComfyUIClient:
    """
    ComfyUI API客户端类，封装了工作流提交、状态监控和结果下载功能。
    """
    WORKFLOW_DIR = "/root/shared-nvme/shuyiwang/MusicVideo_ProduXer/workflows/lipsync.json"
    
    def __init__(self, server_address: str = "localhost:8190", save_dir: str = "./generated_videos"):
        """
        初始化ComfyUI客户端
        
        :param server_address: ComfyUI服务器地址，格式为"host:port"
        """
        self.server_address = server_address
        self.comfy_api_url = f"http://{server_address}"
        self.ws_url = f"ws://{server_address}/ws"
        self.client_id = str(uuid.uuid4())
        self.save_dir = save_dir
        
        # 任务状态跟踪
        self.task_status = {
            "current_node": None,
            "progress": 0,
            "max_progress": 1,
            "status": "pending",  # pending, executing, completed, failed
            "prompt_id": None
        }
        
        # WebSocket相关
        self.websocket_thread = None
        self.should_listen = True

    async def _listen_for_updates(self):
        """
        内部方法：WebSocket监听器，用于实时监控任务状态[1,3](@ref)
        """
        ws_url_with_client = f"{self.ws_url}?clientId={self.client_id}"
        
        try:
            async with websockets.connect(ws_url_with_client) as websocket:
                print(f"WebSocket连接已建立，客户端ID: {self.client_id}")
                
                while self.should_listen:
                    try:
                        raw_message = await websocket.recv()
                        
                        if isinstance(raw_message, bytes):
                            print(f"收到二进制数据，长度: {len(raw_message)}字节")
                            continue
                            
                        data = json.loads(raw_message)
                        message_type = data.get('type')
                        
                        await self._handle_websocket_message(message_type, data)
                        
                    except json.JSONDecodeError as e:
                        print(f"消息JSON解析错误: {e}")
                    except UnicodeDecodeError as e:
                        print(f"消息解码错误: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket连接已关闭")
        except Exception as e:
            print(f"WebSocket监听错误: {e}")

    async def _handle_websocket_message(self, message_type: str, data: Dict[str, Any]):
        """
        处理不同类型的WebSocket消息[1,3](@ref)
        """
        if message_type == 'status':
            status_data = data.get('data', {})
            print(f"队列状态: {status_data}")
            
        elif message_type == 'executing':
            execution_data = data.get('data', {})
            node_id = execution_data.get('node')
            prompt_id_from_msg = execution_data.get('prompt_id')
            
            if node_id is None and prompt_id_from_msg == self.task_status["prompt_id"]:
                print("🎉 任务执行已完成！")
                self.task_status["status"] = "completed"
            elif node_id is not None:
                self.task_status["current_node"] = node_id
                self.task_status["status"] = "executing"
                print(f"正在执行节点: {node_id}")
                
        elif message_type == 'progress':
            progress_data = data.get('data', {})
            self.task_status["progress"] = progress_data.get('value', 0)
            self.task_status["max_progress"] = progress_data.get('max', 1)
            progress_percent = (self.task_status["progress"] / self.task_status["max_progress"]) * 100
            print(f"任务进度: {self.task_status['progress']}/{self.task_status['max_progress']} ({progress_percent:.1f}%)")
            
        elif message_type == 'execution_error':
            error_data = data.get('data', {})
            print(f"❌ 任务执行出错: {error_data}")
            self.task_status["status"] = "failed"

    def _start_websocket_listener(self, prompt_id: str):
        """
        启动WebSocket监听线程[4](@ref)
        """
        self.task_status["prompt_id"] = prompt_id
        self.task_status["status"] = "pending"
        self.should_listen = True
        
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._listen_for_updates())
            loop.close()
        
        self.websocket_thread = threading.Thread(target=run_async)
        self.websocket_thread.daemon = True
        self.websocket_thread.start()
        print("WebSocket监听器已启动")

    def _wait_for_completion(self, timeout: int = 3600) -> str:
        """
        等待任务完成，带有超时机制
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.task_status["status"] in ["completed", "failed"]:
                return self.task_status["status"]
            
            if self.task_status["status"] == "executing":
                progress_percent = (self.task_status["progress"] / self.task_status["max_progress"]) * 100
                print(f"\r当前进度: {progress_percent:.1f}%", end="", flush=True)
            
            time.sleep(1)
        
        print("任务等待超时")
        return "timeout"

    def upload_file(self, file_path: str, file_type: str = "input") -> Dict[str, Any]:
        """
        上传文件到ComfyUI服务器[1](@ref)
        
        :param file_path: 本地文件路径
        :param file_type: 文件类型（input/output/temp）
        :return: 上传文件的信息字典
        """
        file_ext = file_path.split('.')[-1].lower()
        file_name = os.path.basename(file_path)
        
        with open(file_path, "rb") as f:
            files = {'image': (file_name, f, f"{file_type}/{file_ext}")}
            data = {'type': 'input', 'overwrite': 'true'}
            
            response = requests.post(
                f"{self.comfy_api_url}/upload/image", 
                files=files, 
                data=data
            )
            
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def load_workflow(self, workflow_path: Optional[str]) -> Dict[str, Any]:
        """
        加载工作流JSON文件
        """
        if not workflow_path:
            workflow_path = self.WORKFLOW_DIR
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def execute_workflow(self, workflow_json: Dict[str, Any], 
                        input_files: Dict[str, str],
                        params: Dict[str, Any],
                        output_dir: Optional[str]=None,
                        file_name: Optional[str]=None) -> Dict[str, Any]:
        """
        执行ComfyUI工作流[1,3](@ref)
        
        :param workflow_json: 工作流JSON配置
        :param input_files: 输入文件映射 {文件类型: 文件路径}
        :param params: 工作流参数
        :return: 任务执行结果
        """
        # 1. 上传文件
        upload_info = {}
        for file_type, file_path in input_files.items():
            print(f"上传文件: {file_path}")
            upload_info[file_type] = self.upload_file(file_path)
        
        print(f"文件上传完成: {upload_info}")
        
        # 2. 配置工作流参数
        workflow_json["228"]["inputs"]["video"] = upload_info["video"]["name"]
        workflow_json["125"]["inputs"]["audio"] = upload_info["audio"]["name"]
        workflow_json["308"]["inputs"]["start_time"] = params["time"]["start_time"]
        workflow_json["308"]["inputs"]["end_time"] = params["time"]["end_time"]
        if params.get("prompt"):
            if params["prompt"].get("positive"):
                workflow_json["241"]["inputs"]["positive_prompt"] = params["prompt"]["positive"]
            if params["prompt"].get("negative"):
                workflow_json["241"]["inputs"]["negative_prompt"] = params["prompt"]["negative"]
        
        # 3. 提交任务
        payload = {
            "prompt": workflow_json,
            "return_temp_files": False,
            "client_id": self.client_id
        }
        
        response = requests.post(f'{self.comfy_api_url}/prompt', json=payload)
        response.raise_for_status()
        
        result = response.json()
        prompt_id = result["prompt_id"]
        print(f"任务提交成功, Prompt ID: {prompt_id}")
        
        # 4. 启动监听并等待完成
        self._start_websocket_listener(prompt_id)
        final_status = self._wait_for_completion()
        
        if final_status == "completed":
            print("\n任务执行完成")
        elif final_status == "failed":
            print("\n任务执行失败！")
        else:
            print("\n任务状态未知或超时")
            
        # 5. 下载结果
        if not output_dir:
            output_dir=self.save_dir
        saved_paths = self.download_video_result(prompt_id=prompt_id, save_dir=output_dir, file_name=file_name)
        
        return saved_paths

    def download_video_result(self, prompt_id: str, 
                            target_node: str = "131",
                            save_dir: str = None,
                            file_name: str = None) -> List[str]:
        """
        下载生成的视频文件[1](@ref)
        
        :param prompt_id: 任务ID
        :param target_node: 目标节点ID
        :param save_dir: 保存目录
        :return: 下载的文件路径列表
        """
        # 查询历史记录
        history_url = f"{self.comfy_api_url}/history/{prompt_id}"
        response = requests.get(history_url)
        
        if response.status_code != 200:
            print(f"查询历史记录失败！状态码：{response.status_code}")
            return []
        
        history_data = response.json()
        
        # 保存历史记录用于调试
        with open(f"history_{prompt_id}.json", "w") as f:
            json.dump(history_data, f, indent=2)
            
        task_info = history_data.get(prompt_id, {})
        outputs = task_info.get('outputs', {})
        target_output = outputs.get(target_node, {})
        
        # 查找视频文件信息（尝试多个可能的字段）
        video_fields = ['gifs', 'videos', 'images']
        videos_info = []
        
        for field in video_fields:
            if field in target_output:
                videos_info = target_output[field]
                print(f"在字段 '{field}' 中找到视频信息")
                break
        
        if not videos_info:
            print(f"在节点 {target_node} 的输出中未找到视频文件信息")
            return []
        
        # 创建保存目录
        if not save_dir:
            save_dir = self.save_dir
        os.makedirs(save_dir, exist_ok=True)
        saved_files = []
        
        # 下载视频文件
        for video_info in videos_info:
            params = {
                'filename': video_info['filename'],
                'subfolder': video_info.get('subfolder', ''),
                'type': video_info.get('type', 'output')
            }
            
            download_url = f"{self.comfy_api_url}/view"
            response = requests.get(download_url, params=params)
            
            if response.status_code == 200:
                if not file_name:
                    file_name = video_info['filename']
                file_path = os.path.join(save_dir, file_name)
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                saved_files.append(file_path)
                print(f"视频已成功下载: {file_path}")
            else:
                print(f"下载视频失败！状态码：{response.status_code}")
        
        return saved_files

    def stop(self):
        """
        停止客户端，清理资源
        """
        self.should_listen = False
        if self.websocket_thread and self.websocket_thread.is_alive():
            self.websocket_thread.join(timeout=5)
        print("ComfyUI客户端已停止")
        
# 使用重构后的客户端
if __name__ == "__main__":
    # 创建客户端实例
    client = ComfyUIClient("localhost:8190", save_dir = "./nvidiaFuckYou")
    
    try:
        # 准备输入参数
        input_files = {
            "video": "/root/shared-nvme/shuyiwang/MusicVideo_ProduXer/output_final/shot_4_video_20251001_021412.mp4", 
            "audio": "我不明白.mp3",
        }
        
        params = {
            "time": {
                "start_time": "0:00",
                "end_time": "0:01"
            }
        }
        
        # 加载工作流并执行
        workflow = client.load_workflow("workflows/lipsync.json")
        result = client.execute_workflow(workflow, input_files, params, file_name="fuckyou.mp4")
        # result1 = client.execute_workflow(workflow, input_files, params)
        print("任务执行结果:", result)
        
    except Exception as e:
        print(f"执行过程中出错: {e}")
    finally:
        # 确保资源被正确释放
        client.stop()