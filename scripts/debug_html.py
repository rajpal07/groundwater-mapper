
import os

file_path = r"d:\anirudh_kahn\adi_version\generated_map.html"

if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"File length: {len(content)}")
    print(f"Last 100 chars repr: {repr(content[-100:])}")
    
    if "</body>" in content:
        print("Found </body>")
    else:
        print("Did NOT find </body>")
        
    if "</html>" in content:
        print("Found </html>")
    else:
        print("Did NOT find </html>")
        
    # Test replacement
    js_code = "<script>console.log('test');</script>"
    if "</body>" in content:
        new_content = content.replace("</body>", js_code + "\n</body>")
        print("Replaced </body>")
    elif "</html>" in content:
        new_content = content.replace("</html>", js_code + "\n</html>")
        print("Replaced </html>")
    else:
        new_content = content + js_code
        print("Appended to end")
        
    print(f"New content length would be: {len(new_content)}")
else:
    print("File not found")
