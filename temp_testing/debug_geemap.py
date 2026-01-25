import geemap
import box
import xyzservices
import sys

print(f"Python version: {sys.version}")
print(f"geemap version: {geemap.__version__}")
try:
    print(f"python-box version: {box.__version__}")
except AttributeError:
    print(f"python-box has no __version__")

try:
    print(f"xyzservices version: {xyzservices.__version__}")
except AttributeError:
    print(f"xyzservices has no __version__")

try:
    from geemap.foliumap import basemaps
    print("Successfully imported basemaps from geemap.foliumap")
    print(f"basemaps type: {type(basemaps)}")
except Exception as e:
    print(f"Error importing geemap.foliumap: {e}")
