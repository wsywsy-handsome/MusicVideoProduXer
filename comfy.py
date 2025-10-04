import json
import requests
import websockets
import asyncio
import threading
import uuid
import os

CLIENT_ID = str(uuid.uuid4())
COMFY_API_URL = "http://localhost:8190"
WS_URL = f"ws://localhost:8190/ws?clientId={CLIENT_ID}"

# 存储全局状态
task_status = {
    "current_node": None,
    "progress": 0,
    "max_progress": 1,
    "status": "pending",  # pending, executing, completed, failed
    "prompt_id": None
}

async def listen_for_comfyui_updates():
    """
    异步函数：连接到 ComfyUI 的 WebSocket 并监听任务状态更新。[1,6](@ref)
    """
    global task_status
    try:
        async with websockets.connect(WS_URL) as websocket:
            print(f"WebSocket 连接已建立，客户端ID: {CLIENT_ID}")
            
            while True:
                try:
                    # 接收原始消息[3](@ref)
                    raw_message = await websocket.recv()
                    
                    # 判断消息类型并安全处理[6](@ref)
                    if isinstance(raw_message, bytes):
                        # 二进制消息处理（如图片预览等）
                        print(f"收到二进制数据，长度: {len(raw_message)} 字节")
                        # 可以在这里添加二进制数据的特定处理逻辑
                        continue  # 跳过JSON解析
                    else:
                        # 文本消息处理
                        data = json.loads(raw_message)
                    
                    message_type = data.get('type')
                    
                    if message_type == 'status':
                        # 服务器状态信息，例如队列剩余任务数[1](@ref)
                        status_data = data.get('data', {})
                        print(f"队列状态: {status_data}")
                        
                    elif message_type == 'executing':
                        # 任务执行状态消息[1](@ref)
                        execution_data = data.get('data', {})
                        node_id = execution_data.get('node')
                        prompt_id_from_msg = execution_data.get('prompt_id')
                        
                        if node_id is None:
                            # 当 node 为 None 时，表示整个工作流执行完毕[1](@ref)
                            if prompt_id_from_msg == task_status["prompt_id"]:
                                print("🎉 任务执行已完成！")
                                task_status["status"] = "completed"
                                break  # 退出监听循环
                        else:
                            task_status["current_node"] = node_id
                            task_status["status"] = "executing"
                            print(f"正在执行节点: {node_id}")
                            
                    elif message_type == 'progress':
                        # 进度信息[1](@ref)
                        progress_data = data.get('data', {})
                        task_status["progress"] = progress_data.get('value', 0)
                        task_status["max_progress"] = progress_data.get('max', 1)
                        progress_percent = (task_status["progress"] / task_status["max_progress"]) * 100
                        print(f"任务进度: {task_status['progress']}/{task_status['max_progress']} ({progress_percent:.1f}%)")
                        
                    elif message_type == 'execution_error':
                        # 执行错误[1](@ref)
                        error_data = data.get('data', {})
                        print(f"❌ 任务执行出错: {error_data}")
                        task_status["status"] = "failed"
                        break
                        
                    else:
                        # 其他未处理的消息类型
                        print(f"收到消息类型: {message_type}")
                        # 调试时可取消下一行的注释
                        # print(f"消息内容: {data}")
                        
                except json.JSONDecodeError as e:
                    print(f"消息JSON解析错误: {e}")
                    print(f"原始消息内容: {raw_message[:200]}...")  # 打印前200字符用于调试
                    continue  # 继续监听下一条消息
                except UnicodeDecodeError as e:
                    print(f"消息解码错误（已跳过）: {e}")
                    continue  # 继续监听下一条消息
                    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket 连接已关闭: {e}")
    except Exception as e:
        print(f"WebSocket 监听错误: {e}")
        
def start_websocket_listener(prompt_id):
    """
    在新线程中启动 WebSocket 监听器[4](@ref)
    """
    global task_status
    task_status["prompt_id"] = prompt_id
    task_status["status"] = "pending"
    
    def run_async_in_thread():
        # 在新线程中运行异步函数[4](@ref)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(listen_for_comfyui_updates())
        loop.close()
    
    listener_thread = threading.Thread(target=run_async_in_thread)
    listener_thread.daemon = True  # 设置为守护线程，主线程退出时自动结束[4](@ref)
    listener_thread.start()
    print("WebSocket 监听器已启动")
    return listener_thread

def wait_for_task_completion(timeout=3600):
    """
    等待任务完成，带有超时机制
    """
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if task_status["status"] in ["completed", "failed"]:
            return task_status["status"]
        
        # 打印进度信息
        if task_status["status"] == "executing":
            progress_percent = (task_status["progress"] / task_status["max_progress"]) * 100
            print(f"\r当前进度: {progress_percent:.1f}%", end="", flush=True)
        
        time.sleep(1)  # 每秒检查一次
    
    print("任务等待超时")
    return "timeout"




def load_workflow_api_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def call_workflow(workflow_json, params: dict, input_files: dict = None):
    """
    workflow_json: 导出的 API 格式 workflow JSON（Python dict）
    params: 要覆盖或传入节点参数的映射，例如 {"prompt": "一幅风景画", "steps": 30}
    input_files: 可选，若有输入图像或其他依赖文件，则是 { "image": open("in.png", "rb"), ... }
    返回：响应的 JSON（或二进制图像等）
    """
    # 上传输入文件到ComfyUI
    upload_info = {}
    for kind, path in input_files.items():
        file_ext = path.split('.')[-1].lower()
        with open(path, "rb") as f:
            file = {'image': (path.split('/')[-1], f, f"{kind}/{file_ext}")}
            data = {
                'type': 'input',
                'overwrite': 'true'
            }
            resp = requests.post(f"{COMFY_API_URL}/upload/image", files=file, data=data)
            print(resp)
            upload_info[kind] = resp.json()
    print(upload_info)
    
    
    workflow_json["228"]["inputs"]["video"] = upload_info["video"]["name"]
    workflow_json["125"]["inputs"]["audio"] = upload_info["audio"]["name"]
    workflow_json["308"]["inputs"]["start_time"] = params["time"]["start_time"]
    workflow_json["308"]["inputs"]["end_time"] = params["time"]["end_time"]


    payload = {
        "prompt": workflow_json,
        # 其他可选项，例如是否返回中间文件
        "return_temp_files": False,
        "client_id": CLIENT_ID
    }

    response = requests.post(f'{COMFY_API_URL}/prompt', json=payload)
    response.raise_for_status()
    result = response.json()
    prompt_id = result["prompt_id"]
    print(f"任务提交成功, Prompt ID: {prompt_id}")
    
    # 启动WebSocket监听器
    start_websocket_listener(prompt_id)
    
    # 等待任务执行
    final_status = wait_for_task_completion()
    
    if final_status == "completed":
        print("\n任务执行完成")
    elif final_status == "failed":
        print("\n任务执行失败！")
    else:
        print("\n任务状态未知或超时")
    download_video_from_node(prompt_id=prompt_id)
    return result

def download_video_from_node(prompt_id, target_node_id="131", save_directory="./generated_videos"):
    """
    根据 prompt_id 查询任务历史，并下载指定节点生成的视频文件。

    :param prompt_id: 已完成任务的提示ID
    :param target_node_id: 生成视频的目标节点ID，默认为"131"
    :param save_directory: 视频文件保存的本地目录
    :return: 保存到本地的视频文件路径列表
    """
    # 1. 查询任务历史记录
    history_url = f"{COMFY_API_URL}/history/{prompt_id}"
    response = requests.get(history_url)
    
    if response.status_code != 200:
        print(f"查询历史记录失败！状态码：{response.status_code}")
        return []
    
    history_data = response.json()
    with open(f"history_{prompt_id}.json", "w") as f:
        json.dump(history_data, f, indent=2)
    task_info = history_data.get(prompt_id, {})
    outputs = task_info.get('outputs', {})
    
    # 2. 定位到指定的节点输出
    target_node_output = outputs.get(target_node_id, {})
    # 视频信息可能保存在 'videos' 或 'images' 等字段中，具体取决于节点输出格式
    # 这里以 'videos' 为例，请根据你的工作流节点实际输出进行调整
    videos_info_list = target_node_output.get('gifs', [])
    
    if not videos_info_list:
        print(f"在节点 {target_node_id} 的输出中未找到视频文件信息。")
        # 有时视频信息也可能放在 'images' 字段，可以尝试查找
        images_info_list = target_node_output.get('images', [])
        if images_info_list:
            print("但在 'images' 字段中找到了文件信息，尝试将其作为视频下载。")
            videos_info_list = images_info_list
        else:
            return []
    
    # 3. 创建保存目录
    os.makedirs(save_directory, exist_ok=True)
    saved_files = []
    
    # 4. 遍历并下载视频
    for video_info in videos_info_list:
        # 构建下载请求的参数
        params = {
            'filename': video_info['filename'],
            'subfolder': video_info.get('subfolder', ''),
            'type': video_info.get('type', 'output')  # 通常是 'output'
        }
        
        # 发起下载请求
        download_url = f"{COMFY_API_URL}/view"
        response = requests.get(download_url, params=params)
        
        if response.status_code == 200:
            # 构建本地保存路径
            local_file_path = os.path.join(save_directory, video_info['filename'])
            
            # 将二进制内容写入文件
            with open(local_file_path, 'wb') as f:
                f.write(response.content)
            
            saved_files.append(local_file_path)
            print(f"视频已成功下载并保存至：{local_file_path}")
        else:
            print(f"下载视频失败！状态码：{response.status_code}")
    
    return saved_files

if __name__ == "__main__":
    
    input_files = {
        "video": "/root/shared-nvme/shuyiwang/MusicVideo_ProduXer/output_final/shot_7_video_20251001_021412.mp4", 
        "audio": "我不明白.mp3",
    }
    params = {
        "time": {
            "start_time": "0:00",
            "end_time": "0:01"
        }
    }
    wf = load_workflow_api_json(r"workflows/lipsync.json")
    result = call_workflow(wf, params=params, input_files=input_files)
    # 通常 result 会包含输出图像（可能是 base64 编码或临时文件路径）