"""Scene Sentinel - Utilities for identifying and healing corrupted Panda3D scene nodes."""

import math
from panda3d.core import LMatrix4f, NodePath
from utils.logger import logger

class SceneSentinel:
    @staticmethod
    def is_invalid_transform(mat):
        """Checks if a transformation matrix contains non-finite values (NaN or Inf)."""
        if mat is None:
            return False
        for i in range(4):
            for j in range(4):
                val = mat.get_cell(i, j)
                if math.isnan(val) or math.isinf(val):
                    return True
        return False

    @staticmethod
    def heal_node_transform(node_path):
        """Resets a node's transform to identity if it's corrupted."""
        if not isinstance(node_path, NodePath) or node_path.isEmpty():
            return False
        
        try:
            # Check local transform
            if node_path.hasMat() and SceneSentinel.is_invalid_transform(node_path.getMat()):
                logger.warning(f"[SceneSentinel] Healing corrupted local transform for: {node_path}")
                node_path.setMat(LMatrix4f.identMat())
                return True
        except Exception as e:
            logger.error(f"[SceneSentinel] Error healing node {node_path}: {e}")
        
        return False

    @staticmethod
    def audit_and_heal(node_path, Fix=True, depth=0, max_depth=100, label="audit"):
        """Recursively audits a scene graph for corrupted transforms."""
        if depth == 0:
            logger.debug(f"[SceneSentinel] Starting {label} on {node_path}")
            
        if depth > max_depth or not isinstance(node_path, NodePath) or node_path.isEmpty():
            return 0

        healed_count = 0
        if SceneSentinel.heal_node_transform(node_path):
            healed_count += 1

        try:
            for i in range(node_path.getNumChildren()):
                child = node_path.getChild(i)
                healed_count += SceneSentinel.audit_and_heal(child, Fix, depth + 1, max_depth)
        except Exception:
            pass

        if depth == 0 and healed_count > 0:
            logger.info(f"[SceneSentinel] {label} completed. Healed {healed_count} nodes.")
            
        return healed_count

    @staticmethod
    def emergency_scene_dump(root_node, output_path="logs/emergency_scene_dump.txt"):
        """Dumps the scene graph structure and identifies corrupted nodes to a file."""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"--- Emergency Scene Dump ---\n")
                SceneSentinel._dump_recursive(root_node, f, 0)
            logger.info(f"[SceneSentinel] Emergency dump written to {output_path}")
        except Exception as e:
            logger.error(f"[SceneSentinel] Failed to write emergency dump: {e}")

    @staticmethod
    def _dump_recursive(node, file, depth):
        indent = "  " * depth
        name = node.getName()
        corrupted = "[CORRUPTED]" if node.hasMat() and SceneSentinel.is_invalid_transform(node.getMat()) else ""
        file.write(f"{indent}{name} {corrupted}\n")
        
        for i in range(node.getNumChildren()):
            SceneSentinel._dump_recursive(node.getChild(i), file, depth + 1)
