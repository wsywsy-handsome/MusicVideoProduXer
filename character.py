import datetime
from pathlib import Path
from typing import Optional
from SeedreamImageGenerator import SeedreamImageGenerator 

class CharacterReference:
    """
    角色参考图生成器
    
    用于生成和保存角色参考图像，封装了与Seedream图像生成API的交互逻辑。
    
    Attributes:
        description (str): 角色描述文本
        output_dir (Path): 输出目录路径
        seedream (SeedreamImageGenerator): 图像生成客户端
        image_path (Optional[str]): 已生成图像的保存路径
    """
    # 默认的保存地址
    DEFAULT_OUTPUT_DIR = "outputs"
    
    def __init__(
        self, 
        seedream_client: SeedreamImageGenerator, 
        character_config: str, 
        output_dir: str = DEFAULT_OUTPUT_DIR
    ) -> None:
        """
        初始化角色参考生成器
        
        Args:
            seedream_client: Seedream图像生成客户端实例
            character_config: 角色描述配置文本
            output_dir: 图像输出目录，默认为'outputs'
            
        Raises:
            ValueError: 当必需参数为None或空时
        """
        # 基本设置
        self.description = character_config
        
        # 保存地址设置
        self.output_dir = Path(output_dir)
        self._initialize_output_directory()

        # API 客户端
        self.seedream = seedream_client

        # 中间结果
        self.image_path: Optional[str] = None
        
    def _initialize_output_directory(self) -> None:
        """创建输出目录，确保目录存在[8](@ref)"""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise PermissionError(f"没有权限创建输出目录: {self.output_dir}") from e
        except OSError as e:
            raise OSError(f"创建输出目录失败: {e}") from e
        
    def _generate_filename(self) -> str:
        """生成基于时间戳的唯一文件名[8](@ref)"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"character_reference_{timestamp}.png"
    
    def generate_image(self, prompt: Optional[str] = None, filename: Optional[str] = None) -> str:
        """
        生成角色参考图像
        
        Args:
            prompt: 生成提示词，如为None则使用角色描述
            filename: 输出文件名，如为None则自动生成
            
        Returns:
            生成的图像文件路径
            
        Raises:
            RuntimeError: 图像生成或保存失败时
        """
        final_prompt = prompt or self.description
        final_filename = filename or self._generate_filename()
        save_path = str(self.output_dir / final_filename)
        
        try:
            # 调用API生成图像[1](@ref)
            image_url = self.seedream.generate_image(prompt=final_prompt, size='2K')
            
            # 保存图像到本地
            self.seedream.save_image_from_url(image_url, save_path)
            self.image_path = save_path
            
            print(f"✅ 角色参考图已保存: {save_path}")
            return save_path
            
        except Exception as e:
            error_msg = f"生成角色参考图失败: {str(e)}"
            print(f"❌ {error_msg}")
            raise RuntimeError(error_msg) from e