import gradio as gr
from shots_manager import ShotsManager
from concurrent.futures import ThreadPoolExecutor, as_completed
from shot import Shot
from typing import List, Dict, Any
import os
import asyncio

class MVGeneratorUI:
    def __init__(self, shots_json_path: str = "shots.json"):
        self.manager = ShotsManager(shots_json_path)
        self.current_shots_data = []
        self.script_json_dir = shots_json_path
        # 分镜的图片展示和视频展示与其shot对应的地址由字典维护
        self.shot_components = {i:{"img_output":None, "vid_output":None} for i, shot in enumerate(self.manager.shots)}
    
    def initialize_manager(self):
        """初始化管理器"""
        try:
            self.manager = ShotsManager(self.script_json_dir)
            return "✅ 管理器初始化成功"
        except Exception as e:
            return f"❌ 初始化失败: {str(e)}"
    
    def list_shots(self) -> List[List[Any]]:
        """获取分镜列表数据"""
        self.current_shots_data = []
        for shot in self.manager.shots:
            self.current_shots_data.append([
                shot.id,
                shot.lyric,
                shot.stable_prompt,
                shot.dynamic_prompt,
                shot.duration,
                shot.sing
            ])
        return self.current_shots_data
    
    def generate_reference(self):
        """生成角色参考图"""
        try:
            path = self.manager.generate_reference()
            return path, "✅ 角色参考图生成成功"
        except Exception as e:
            return None, f"❌ 生成失败: {str(e)}"
    
    def batch_generate_first_frames(self):
        """并发生成所有分镜的修改参考图"""
        if not self.manager or not hasattr(self.manager, "shots"):
            return "❌ 请先初始化 manager"

        results = []
        new_images = [None] * len(self.manager.shots)
        # 如果没有参考图片, 抛出错误
        if not self.manager.reference_pic_dir:
            return "❌ 请先生成全局参考形象"
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 只提交 character_in_scene 为 True 的 shot
            futures = {
                executor.submit(
                    self.manager.generate_first_frame,
                    shot_index=i,
                    reference_dir=self.manager.reference_pic_dir,
                    prompt=shot.stable_prompt
                ): (i, shot.id)
                for i, shot in enumerate(self.manager.shots) if getattr(shot, "character_in_scene", False)
            }
            for future in as_completed(futures):
                idx, sid = futures[future]
                try:
                    future.result()
                    results.append(f"✅ 分镜 {sid} 参考图生成成功")
                    new_images[idx] = self.manager.shots[idx].image_path                
                except Exception as e:
                    results.append(f"❌ 分镜 {sid} 失败: {str(e)}")
        for i, shot in enumerate(self.manager.shots):
            if not getattr(shot, "character_in_scene", False):
                results.append(f"⏭️ 分镜 {shot.id} 跳过（无角色）")
        # 只返回具有"图像预览模块"new_images:
        new_images = [new_images[i] for i in range(len(new_images)) if self.shot_components[i]["img_output"]]
        return ["\n".join(results)] + new_images

    def batch_generate_videos(self):
        """并发生成所有分镜的视频"""
        if not self.manager or not hasattr(self.manager, "shots"):
            return "❌ 请先初始化 manager"

        results = []
        new_videos = [None] * len(self.manager.shots)
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {
                executor.submit(
                    shot.generate_video,
                    prompt=self.manager.prompts[i]["vid"],
                    duration=shot.duration,
                    use_image=shot.character_in_scene
                ): (i, shot.id)
                for i, shot in enumerate(self.manager.shots)
            }
            for future in as_completed(futures):
                idx, sid = futures[future]
                try:
                    future.result()
                    results.append(f"✅ 分镜 {sid} 视频生成成功")
                    new_videos[idx] = self.manager.shots[idx].video_path
                except Exception as e:
                    results.append(f"❌ 分镜 {sid} 失败: {str(e)}")
        return ["\n".join(results)] + new_videos
    
    
    def create_shot_management_section(self) -> gr.Blocks:
        """创建分镜管理部分（角色参考 + 分镜列表）"""
        with gr.Blocks() as section:
            gr.Markdown("## 🎭 角色参考与分镜管理")
            
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 角色参考图")
                    ref_btn = gr.Button("生成角色参考图", variant="primary")
                    ref_status = gr.Textbox(label="状态", interactive=False)
                    ref_img = gr.Image(label="角色参考图", type="filepath", height=500)
                
                with gr.Column(scale=2):
                    gr.Markdown("### 分镜列表")
                    with gr.Row():
                        load_btn = gr.Button("刷新分镜列表", variant="secondary")
                        init_btn = gr.Button("重新初始化", variant="secondary")
                    
                    init_status = gr.Textbox(label="初始化状态", interactive=False)
                    shots_table = gr.Dataframe(
                        value=self.list_shots,
                        headers=["ID", "歌词", "静态Prompt", "动态Prompt", "时长", "是否唱歌"],
                        datatype=["number", "str", "str", "str", "number", "bool"],
                        interactive=False,
                        max_height=500
                    )
            
            # 事件绑定
            ref_btn.click(
                fn=self.generate_reference,
                outputs=[ref_img, ref_status]
            )
            
            load_btn.click(
                fn=self.list_shots,
                outputs=shots_table
            )
            
            init_btn.click(
                fn=self.initialize_manager,
                outputs=init_status
            ).then(
                fn=self.list_shots,
                outputs=shots_table
            )
        
        return section
    
    def create_batch_control_section(self) -> gr.Blocks:
        """"创建批量管理区: """
        num_6s = 0
        num_10s = 0
        num_to_be_edited = 0
        for shot in self.manager.shots:
            if shot.duration <= 6:
                num_6s += 1
            else:
                num_10s += 1
            if shot.character_in_scene:
                num_to_be_edited += 1
        with gr.Blocks() as section:
            gr.Markdown("## 👥 批量管理 (以保存过的prompt为准)")
            
            with gr.Row():
                batch_fir_btn = gr.Button(f"一键生成第一帧 💰估价: ¥{0.2*num_to_be_edited}", variant="secondary")
                batch_vid_btn = gr.Button(f"一键生成所有视频 💰估价: ¥{2*num_6s+4*num_10s}", variant="secondary")
            batch_status = gr.Textbox(label="批量任务状态", interactive=False, lines=10)
        print(self.shot_components)
        batch_fir_btn.click(
            fn=self.batch_generate_first_frames,
            outputs=[batch_status] + [self.shot_components[i]["img_output"] for i in range(len(self.manager.shots))if self.shot_components[i]["img_output"]]
        )
        batch_vid_btn.click(
            fn=self.batch_generate_videos,
            outputs=[batch_status] + [self.shot_components[i]["vid_output"] for i in range(len(self.manager.shots))]
        )
        
    def create_shot_detail_section(self, shot_index: int) -> gr.Blocks:
        """为单个shot创建详细操作页面"""
        shot = self.manager.shots[shot_index]
        shot_id = shot.id
        with gr.Blocks() as section:
            gr.Markdown(f"## 🎬 分镜 {shot_id} 详情")
            
            with gr.Row():
                gr.Markdown(f"**歌词:** {shot.lyric}")
                gr.Markdown(f"**时长:** {shot.duration}秒")
                gr.Markdown(f"**唱歌:** {'是' if shot.sing else '否'}")
            
            with gr.Tabs():
                if shot.character_in_scene: 
                    # Tab 1: 图像生成
                    with gr.TabItem("🖼️ 图像生成"):
                        with gr.Row():
                            with gr.Column():
                                gr.Markdown("### 修改第一帧图像")
                                edit_img_input = gr.Image(
                                    label="上传参考图进行修改",
                                    type="filepath",
                                    height=200,
                                    value=self.manager.reference_pic_dir
                                )
                                edit_prompt = gr.Textbox(
                                    label="修改Prompt (可选)",
                                    value=shot.stable_prompt,
                                    lines=2
                                )
                                edit_img_btn = gr.Button("修改图像", variant="secondary")
                                edit_status = gr.Textbox(label="状态", interactive=False)
                        
                        img_output = gr.Image(
                            label="图像预览",
                            type="filepath",
                            height=400,
                            value=shot.image_path
                        )
                        # 保存组件引用
                        self.shot_components[shot_index]["img_output"] = img_output
                        print(f"shot_{shot_index} initialized!")
                        
                        # 图像修改事件
                        
                        edit_img_btn.click(
                            fn=lambda img, prompt: self._edit_first_frame(shot_index, img, prompt),
                            inputs=[edit_img_input, edit_prompt],
                            outputs=[img_output, edit_status]
                        )
                
                # Tab 2: 视频生成
                with gr.TabItem("🎥 视频生成"):
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("### 生成视频")
                            # 如果角色不在分镜中, 就由hailuo掌管所有提示词
                            if shot.character_in_scene:
                                prompt = shot.dynamic_prompt
                            else:
                                prompt = shot.stable_prompt + shot.dynamic_prompt
                            video_prompt = gr.Textbox(
                                label="视频Prompt (可选)",
                                value=prompt,
                                lines=2
                            )
                            
                            video_duration = gr.Number(
                                label="视频时长(秒, 6s以下生成6s, 6s以上生成10s)",
                                value=shot.duration
                            )
                            video_btn = gr.Button("生成视频 (prompt以文本框中为准)", variant="primary")
                            video_status = gr.Textbox(label="状态", interactive=False)
                        
                        with gr.Column():
                            gr.Markdown("### Prompt说明")
                            gr.Markdown(f"**静态Prompt:** {shot.stable_prompt}")
                            gr.Markdown(f"**动态Prompt:** {shot.dynamic_prompt}")
                            # 提供修改和恢复视频提示词的按钮
                            save_video_prompt = gr.Button("保存提示词 (不会修改原始json)")
                            restore_video_prompt = gr.Button("恢复默认提示词")
                            edit_video_prompt_output = gr.Textbox(label="修改结果", interactive=False)
                            save_video_prompt.click(
                                fn=lambda prompt: self._edit_prompt(True, prompt, shot_index),
                                inputs=video_prompt,
                                outputs=edit_video_prompt_output
                            )
                            #提供回复默认视频提示词的按钮
                            restore_video_prompt.click(
                                fn=lambda: (
                                    self._restore_prompt(True, shot_index),
                                    shot.dynamic_prompt if shot.character_in_scene else f"{shot.stable_prompt}, {shot.dynamic_prompt}"
                                ),
                                outputs=[edit_video_prompt_output, video_prompt]
                            )
                        # 对口型按钮
                        lip_sync_btn = gr.Button("对口型", variant="primary")
                        lip_sync_status = gr.Textbox(label="状态", interactive=False)
                    
                    video_output = gr.Video(
                        label="视频预览",
                        height=400,
                        value=shot.video_path
                    )
                    
                    lip_sync_output = gr.Video(
                        label="视频预览",
                        height= 400,
                        value=shot.lip_sync_path
                    )
                    
                    # 保存组件引用
                    self.shot_components[shot_index]["vid_output"] = video_output
                    
                    # 事件绑定
                    video_btn.click(
                        fn=lambda prompt, duration: self._generate_video(shot_index, prompt, duration, shot.character_in_scene),
                        inputs=[video_prompt, video_duration],
                        outputs=[video_output, video_status]
                    )
                    lip_sync_btn.click(
                        fn=lambda : self._lip_sync(shot_index),
                        outputs=[lip_sync_output, lip_sync_status]
                    )
                    
                    
        
        return section
    
    def _generate_image(self, shot_index: int, prompt: str = None):
        """生成图像（内部方法）"""
        try:
            shot = self.manager.shots[shot_index]
            shot_id = shot.id
            path = shot.generate_image(prompt=prompt)
            return path, f"✅ 分镜 {shot_id} 图像生成成功"
        except Exception as e:
            return None, f"❌ 图像生成失败: {str(e)}"
    
    def _edit_first_frame(self, shot_index: int, base_img: str=None, prompt: str = None):
        """修改第一帧图像（内部方法）"""
        try:
            shot=self.manager.shots[shot_index]
            shot_id = shot.id
            path = self.manager.generate_first_frame(shot_index=shot_index, reference_dir=base_img, prompt=prompt)
            return path, f"✅ 分镜 {shot_id} 图像修改成功"
        except Exception as e:
            return None, f"❌ 图像修改失败: {str(e)}"
    
    def _generate_video(self, shot_index: int, prompt: str = None, duration: float = None, character_in_scene: bool = True):
        """生成视频（内部方法）"""
        try:
            shot = self.manager.shots[shot_index]
            shot_id = shot.id
            path = shot.generate_video(prompt=prompt, duration=duration, use_image=character_in_scene, )
            return path, f"✅ 分镜 {shot_id} 视频生成成功"
        except Exception as e:
            return None, f"❌ 视频生成失败: {str(e)}"
    def _lip_sync(self, shot_index: int):
        try:
            shot = self.manager.shots[shot_index]
            saved_paths = shot.video_lip_sync(
                audio_path = "/root/shared-nvme/shuyiwang/MusicVideo_ProduXer/我不明白.mp3",
            )
            return str(saved_paths[-1]), f"done!"
        except Exception as e:
            return None, f"failed!{str(e)}"
    
    def _edit_prompt(self, is_video_prompt:bool, prompt:str, index:int):
        if is_video_prompt:
            self.manager.prompts[index]["vid"]=prompt
            return f"分镜index=={index}的视频🎬提示词已保存修改!"
    def _restore_prompt(self, is_video_prompt:bool, index:int):
        shot = self.manager.shots[index]
        if is_video_prompt:
            self.manager.prompts[index]["vid"]=shot.dynamic_prompt if shot.character_in_scene else f"{shot.stable_prompt}, {shot.dynamic_prompt}"
            return f"分镜index=={index}的视频🎬提示词已恢复默认!"
    
        
    def create_ui(self) -> gr.Blocks:
        """创建完整的UI界面"""
        with gr.Blocks(theme=gr.themes.Soft(), title="MV分镜生成工具") as demo:
            gr.Markdown("# 🎬 MV 分镜生成管理工具")
            
            # 主管理区域
            management_section = self.create_shot_management_section()
            # 批量任务管理区域
            # 为每个shot创建独立Tab
            if hasattr(self.manager, 'shots') and self.manager.shots:
                gr.Markdown("## 📋 分镜详细操作")
                
                with gr.Tabs() as tabs:
                    # 为每个shot创建一个Tab
                    for shot_index, shot in enumerate(self.manager.shots):
                        print(shot.start_time)
                        with gr.Tab(f"分镜 {shot.id}"):
                            self.create_shot_detail_section(shot_index=shot_index)
            batch_section = self.create_batch_control_section()
            return demo

# 使用示例
if __name__ == "__main__":
    # 创建UI实例
    ui = MVGeneratorUI("shots.json")
    
    # 生成UI并启动
    demo = ui.create_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )