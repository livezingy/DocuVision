"""
Compatibility patches for PaddleOCR 3.1.x and PaddlePaddle 3.0.0
This module should be imported early in the initialization process
"""

import os
import sys
from importlib import metadata
from loguru import logger

# Set environment variables BEFORE importing Paddle
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_onednn'] = '0'
os.environ['MKLDNN_ENABLED'] = '0'
os.environ['FLAGS_use_onednn'] = '0'
os.environ['PADDLE_USE_ONEDNN'] = '0'


def _get_dist_version(dist_names: list[str]) -> str:
    """Get installed package version without importing the package."""
    for name in dist_names:
        try:
            return metadata.version(name)
        except Exception:
            continue
    return "0.0.0"


def _parse_version_tuple(version_str: str) -> tuple[int, int, int]:
    """Parse 'X.Y.Z...' into (X, Y, Z). Non-numeric suffixes are ignored."""
    core_chars: list[str] = []
    for ch in version_str:
        if ch.isdigit() or ch == ".":
            core_chars.append(ch)
        else:
            break
    core = "".join(core_chars)
    parts = [p for p in core.split(".") if p]
    nums: list[int] = []
    for p in parts:
        try:
            nums.append(int(p))
        except Exception:
            break
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def _should_apply_legacy_patches() -> bool:
    """
    Decide whether to apply legacy monkey patches.

    Legacy patches are only required for known-problematic combinations:
    - PaddlePaddle 3.0.0 + PaddleOCR 3.1.x
    """
    paddle_ver = _parse_version_tuple(_get_dist_version(["paddlepaddle", "paddlepaddle-gpu"]))
    paddleocr_ver = _parse_version_tuple(_get_dist_version(["paddleocr"]))
    return paddle_ver == (3, 0, 0) and paddleocr_ver[0] == 3 and paddleocr_ver[1] == 1


def apply_paddle_patches():
    """Apply patches for missing PaddlePaddle 3.0.0 functions"""
    try:
        import paddle.incubate.nn.functional as functional_module

        # Patch 1: fused_rms_norm_ext
        if not hasattr(functional_module, 'fused_rms_norm_ext'):
            def fused_rms_norm_ext(x, weight, bias, eps):
                import paddle
                return paddle.nn.functional.layer_norm(x, weight.shape, weight=weight, bias=bias, eps=eps)
            functional_module.fused_rms_norm_ext = fused_rms_norm_ext
            logger.debug("[PATCH] paddle.incubate.nn.functional.fused_rms_norm_ext applied")

        # Patch 2: cal_aux_loss
        if not hasattr(functional_module, 'cal_aux_loss'):
            def cal_aux_loss(x, y, weight=None, reduction='mean'):
                import paddle
                return paddle.nn.functional.mse_loss(x, y, reduction=reduction)
            functional_module.cal_aux_loss = cal_aux_loss
            logger.debug("[PATCH] paddle.incubate.nn.functional.cal_aux_loss applied")

        return True
    except Exception as e:
        logger.warning(f"[PATCH] Failed to apply Paddle patches: {e}")
        return False


def apply_paddlex_patches():
    """Apply patches for PaddleX 3.x compatibility issues"""
    try:
        # Patch PaddlePredictorOption to accept positional arguments
        from paddlex.inference import PaddlePredictorOption

        original_init = PaddlePredictorOption.__init__

        def fixed_init(self, device_type=None, device_id=None, **kwargs):
            """Fixed __init__ that handles both positional and keyword arguments"""
            # Accept both positional and keyword arguments
            # Then call original init with keyword arguments only
            init_kwargs = {'device_type': device_type, 'device_id': device_id}
            init_kwargs.update(kwargs)

            # Filter out None values
            init_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}

            # Try to call original with filtered kwargs
            try:
                original_init(self, **init_kwargs)
            except TypeError:
                # If original init still fails, try with empty call
                try:
                    original_init(self)
                except:
                    pass

        PaddlePredictorOption.__init__ = fixed_init
        logger.debug("[PATCH] PaddleX PaddlePredictorOption.__init__ patched to accept positional args")
        return True
    except Exception as e:
        logger.warning(f"[PATCH] Failed to apply PaddleX patches: {e}")
        return False


def apply_paddleocr_patches():
    """Apply patches for PaddleOCR 3.1.x compatibility issues"""
    try:
        if not _should_apply_legacy_patches():
            logger.debug("[PATCH] Skipping legacy PaddleOCR patches (not required for this environment)")
            return True

        # Patch 1: Fix prepare_common_init_args bug - NO LONGER NEEDED if PaddlePredictorOption is fixed
        # But we can still apply it as a belt-and-suspenders approach

        from paddleocr import _common_args

        original_prepare = _common_args.prepare_common_init_args

        # Only patch if not already patched
        if not hasattr(_common_args.prepare_common_init_args, '_is_patched'):
            def fixed_prepare(model_name, common_args):
                """Fixed version that uses kwargs only"""
                try:
                    # Import here to avoid circular imports
                    from paddlex.inference import PaddlePredictorOption
                    from paddlex.utils.device import get_default_device, parse_device

                    device = common_args.get("device") or get_default_device()
                    device_type, device_ids = parse_device(device)
                    device_id = device_ids[0] if device_ids else None

                    # Use keyword arguments only
                    pp_option = PaddlePredictorOption(
                        device_type=device_type,
                        device_id=device_id
                    )

                    # Setup other options
                    if device_type == "gpu":
                        use_pptrt = common_args.get("use_pptrt", False)
                        if use_pptrt:
                            pptrt_precision = common_args.get("pptrt_precision", "fp16")
                            if pptrt_precision == "fp32":
                                pp_option.run_mode = "trt_fp32"
                            else:
                                pp_option.run_mode = "trt_fp16"
                        else:
                            pp_option.run_mode = "paddle"
                    else:
                        pp_option.run_mode = "paddle"

                    init_kwargs = {
                        "use_hpip": common_args.get("enable_hpi", True),
                        "hpi_config": {
                            "device_type": device_type,
                            "device_id": device_id,
                        }
                    }

                    # Keep return type compatible with PaddleOCR pipelines: return kwargs dict.
                    init_kwargs["pp_option"] = pp_option
                    return init_kwargs
                except Exception as e:
                    logger.error(f"[PATCH] Fixed prepare_common_init_args failed: {e}")
                    # Fall back to original
                    return original_prepare(model_name, common_args)

            _common_args.prepare_common_init_args = fixed_prepare
            fixed_prepare._is_patched = True
            logger.debug("[PATCH] paddleocr._common_args.prepare_common_init_args patched")

        return True
    except Exception as e:
        logger.warning(f"[PATCH] Failed to apply PaddleOCR patches: {e}")
        return False


def apply_all_patches():
    """Apply all compatibility patches"""
    if _should_apply_legacy_patches():
        logger.info("[PATCH] Applying legacy compatibility patches (Paddle 3.0.0 + PaddleOCR 3.1.x)...")
    else:
        logger.info("[PATCH] Compatibility patches: legacy patches not required for this environment")

    # Apply patches in order
    paddle_ok = apply_paddle_patches()
    # Skip paddlex patches for now - they require more work to avoid signature conflicts
    # paddlex_ok = apply_paddlex_patches()
    paddleocr_ok = apply_paddleocr_patches()

    if paddle_ok and paddleocr_ok:
        logger.info("[PATCH] All compatibility patches applied successfully")
        return True
    else:
        logger.warning("[PATCH] Some patches failed to apply")
        return False


# NOTE: DO NOT auto-apply patches here!
# Patches are manually applied in main.py to avoid multiple PaddleX initializations
