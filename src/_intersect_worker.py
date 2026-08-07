"""Subprocess worker for parallel cone-intersect.

Isolated in its own module so multiprocessing (Windows uses `spawn`) doesn't
re-trigger the heavy geometry build in `pot.py` inside every child process —
importing this module is essentially free.
"""

def intersect_worker(proxy_path: str, add_path: str, out_path: str) -> None:
    """Read proxy + additive slices as BREP files, intersect, write result
    as BREP. Called in a child process from `pot._parallel_cone_intersect`."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape

    b = BRep_Builder()
    proxy_s = TopoDS_Shape()
    add_s   = TopoDS_Shape()
    BRepTools.Read_s(proxy_s, proxy_path, b)
    BRepTools.Read_s(add_s,   add_path,   b)

    algo = BRepAlgoAPI_Common(proxy_s, add_s)
    algo.Build()
    BRepTools.Write_s(algo.Shape(), out_path)
