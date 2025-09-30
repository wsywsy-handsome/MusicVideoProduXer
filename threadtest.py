from shots_manager import ShotsManager
import concurrent.futures
import os

def process_shot(shotmanager: ShotsManager, id: int, description_dir):
    shotmanager.generate_first_frame(shot_index=id, reference_dir=description_dir)
    
    return f"Completed processing shot {id}"

if __name__ == "__main__":
    manager = ShotsManager("shoted.json", output_dir="output5")

    # 列出所有 shots
    manager.list_shots()

    description_dir = manager.generate_reference()
    
    # 使用线程池并行处理
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 提交所有shot的处理任务
        futures = [executor.submit(process_shot, manager,id+1, None) for id in range(len(manager.shots))]
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            print(result)
           