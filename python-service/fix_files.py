import os

filepath = r'd:\anirudh_kahn\Final_Groundwater_next_site\groundwater-mapper_pushed\python-service\api\routes\health.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''            "llama_cloud_key": bool(os.getenv("LLAMA_CLOUD_API_KEY"))
        }
    )'''

replacement = '''            "llama_cloud_key": bool(os.getenv("LLAMA_CLOUD_API_KEY"))
        },
        llamaparse=bool(os.getenv("LLAMA_CLOUD_API_KEY")),
        gee=os.getenv("EARTHENGINE_TOKEN") is not None
    )'''

normalized_content = content.replace('\r\n', '\n')
new_content = normalized_content.replace(target, replacement)
    
with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content)
print("Updated health.py")

filepath_parser = r'd:\anirudh_kahn\Final_Groundwater_next_site\groundwater-mapper_pushed\python-service\api\services\excel_parser.py'
with open(filepath_parser, 'r', encoding='utf-8') as f:
    content_parser = f.read()

target_parser = '''            parser = LlamaParse(
                api_key=self.llama_cloud_api_key,
                result_type="dataframe",
                verbose=False
            )'''
replacement_parser = '''            parser = LlamaParse(
                api_key=self.llama_cloud_api_key,
                result_type="text",
                verbose=False
            )'''
normalized_parser = content_parser.replace('\r\n', '\n')
new_content_parser = normalized_parser.replace(target_parser, replacement_parser)

target_split = '''                            # Simple parsing - may need adjustment based on actual output
                            parts = line.split('\\t')
                            if len(parts) > 1:
                                data.append(parts)'''

replacement_split = '''                            # Simple parsing - may need adjustment based on actual output
                            parts = [p.strip() for p in line.split('\\t') if p.strip()]
                            if len(parts) > 1:
                                data.append(parts)'''
new_content_parser = new_content_parser.replace(target_split, replacement_split)

with open(filepath_parser, 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content_parser)
print("Updated excel_parser.py")
