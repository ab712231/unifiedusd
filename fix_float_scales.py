from pxr import Usd, Gf
import glob
import os

search_dir = os.path.dirname(os.path.abspath(__file__))

for usd_file in glob.glob(os.path.join(search_dir, "**/*.usd*"), recursive=True):
    try:
        stage = Usd.Stage.Open(usd_file)
        modified = False
        for prim in stage.Traverse():
            sa = prim.GetAttribute("xformOp:scale")
            if sa and sa.IsValid():
                val = sa.Get()
                if isinstance(val, float):
                    print(f"FOUND float scale: {usd_file} @ {prim.GetPath()} = {val}")
                    sa.Set(Gf.Vec3d(val, val, val))
                    modified = True
        if modified:
            stage.Save()
            print("  Saved.")
    except Exception as e:
        print(f"  Skipped {usd_file}: {e}")

print("Done")
