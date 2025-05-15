#!/usr/bin/env python3
"""
Enhanced Debug Logging Utilities for MCP Server

This module provides enhanced debugging tools for the MCP server.
It adds logging and inspection functions to help trace execution flow
when VSCode breakpoints aren't triggering properly.

Usage:
    from mcp.enhanced_debug_logging import log_debug_point, log_json_rpc_request, log_method_call
    
    # Add to any function or method you want to trace
    def some_method():
        log_debug_point()
        # Method code...
    
    # Add to request handlers to log incoming JSON-RPC requests
    async def handle_jsonrpc(self, request):
        log_json_rpc_request(await request.json())
        # Handler code...
"""

import inspect
import json
import logging
import os
import sys
import traceback
from typing import Any, Dict, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp.debug")

# Set debug level based on environment variable
if os.environ.get("MCP_DEBUG", "false").lower() == "true":
    logger.setLevel(logging.DEBUG)

def log_debug_point(inspect_locals: bool = False, message: Optional[str] = None) -> None:
    """
    Log a debug point with current file and line information.
    
    Args:
        inspect_locals: If True, logs local variables
        message: Optional custom message
    """
    try:
        # Get current frame info for accurate source location
        current_frame = inspect.currentframe()
        caller_frame = current_frame.f_back
        frame_info = inspect.getframeinfo(caller_frame)
        
        # Construct basic message
        log_msg = f"DEBUG POINT: {frame_info.filename}:{frame_info.lineno}"
        
        # Add function name if available
        if frame_info.function:
            log_msg += f" in {frame_info.function}()"
            
        # Add custom message if provided
        if message:
            log_msg += f" - {message}"
        
        # Log the debug point
        logger.debug(log_msg)
        
        # Log local variables if requested
        if inspect_locals and caller_frame.f_locals:
            locals_str = "\nLOCAL VARIABLES:\n"
            for name, value in caller_frame.f_locals.items():
                if name.startswith('__'):
                    continue  # Skip internal variables
                    
                # Format complex objects safely
                if hasattr(value, '__dict__'):
                    # For objects, show type and a few attributes
                    try:
                        value_str = f"{type(value).__name__} object"
                        attrs = {}
                        for attr, attr_val in vars(value).items():
                            if not attr.startswith('_') and not callable(attr_val):
                                attrs[attr] = str(attr_val)[:50]  # Limit length
                        if attrs:
                            value_str += f" with attrs: {attrs}"
                    except:
                        value_str = f"{type(value).__name__} (unprintable)"
                else:
                    # For simple types
                    try:
                        value_str = str(value)[:100]  # Limit length
                        if len(str(value)) > 100:
                            value_str += "..."
                    except:
                        value_str = f"{type(value).__name__} (unprintable)"
                
                locals_str += f"  {name} = {value_str}\n"
                
            logger.debug(locals_str)
    except Exception as e:
        logger.error(f"Error in log_debug_point: {e}")

def log_json_rpc_request(data: Dict[str, Any]) -> None:
    """
    Log detailed information about a JSON-RPC request.
    
    Args:
        data: The JSON-RPC request data
    """
    try:
        logger.debug("===== JSON-RPC REQUEST =====")
        logger.debug(f"Method: {data.get('method', 'unknown')}")
        logger.debug(f"ID: {data.get('id', 'none')}")
        
        # Handle params specially
        params = data.get('params', {})
        if isinstance(params, dict):
            logger.debug("Params:")
            for key, value in params.items():
                # Format the value based on its type
                if isinstance(value, dict) and key == 'arguments':
                    logger.debug(f"  {key}:")
                    for arg_key, arg_val in value.items():
                        if isinstance(arg_val, str) and len(arg_val) > 100:
                            logger.debug(f"    {arg_key}: {arg_val[:100]}... (truncated)")
                        else:
                            logger.debug(f"    {arg_key}: {arg_val}")
                else:
                    if isinstance(value, str) and len(value) > 100:
                        logger.debug(f"  {key}: {value[:100]}... (truncated)")
                    else:
                        logger.debug(f"  {key}: {value}")
        else:
            logger.debug(f"Params: {params}")
            
        logger.debug("===========================")
    except Exception as e:
        logger.error(f"Error in log_json_rpc_request: {e}")

def log_method_call(func):
    """
    Decorator to log method entry and exit with parameters and return values.
    
    Args:
        func: The function to decorate
        
    Returns:
        Wrapped function that logs calls
    """
    async def async_wrapper(*args, **kwargs):
        try:
            # Get caller info
            frame = inspect.currentframe().f_back
            caller_info = inspect.getframeinfo(frame)
            
            # Log method entry
            logger.debug(f"ENTER {func.__name__} called from {caller_info.filename}:{caller_info.lineno}")
            
            # Format arguments (excluding self for methods)
            arg_str = []
            for i, arg in enumerate(args):
                if i == 0 and arg.__class__.__name__ == args[0].__class__.__name__:
                    # This is likely 'self' - skip it in the log
                    continue
                    
                # Format the argument
                try:
                    arg_repr = repr(arg)
                    if len(arg_repr) > 50:
                        arg_repr = arg_repr[:50] + "..."
                    arg_str.append(arg_repr)
                except:
                    arg_str.append(f"{type(arg).__name__}")
            
            # Format keyword arguments
            for key, val in kwargs.items():
                try:
                    val_repr = repr(val)
                    if len(val_repr) > 50:
                        val_repr = val_repr[:50] + "..."
                    arg_str.append(f"{key}={val_repr}")
                except:
                    arg_str.append(f"{key}={type(val).__name__}")
                    
            logger.debug(f"  Arguments: {', '.join(arg_str)}")
            
            # Call the function
            result = await func(*args, **kwargs)
            
            # Log the result
            try:
                result_repr = repr(result)
                if len(result_repr) > 100:
                    result_repr = result_repr[:100] + "..."
            except:
                result_repr = f"{type(result).__name__}"
                
            logger.debug(f"EXIT {func.__name__} with result: {result_repr}")
            return result
            
        except Exception as e:
            logger.error(f"ERROR in {func.__name__}: {str(e)}")
            logger.debug(traceback.format_exc())
            raise
            
    def sync_wrapper(*args, **kwargs):
        try:
            # Get caller info
            frame = inspect.currentframe().f_back
            caller_info = inspect.getframeinfo(frame)
            
            # Log method entry
            logger.debug(f"ENTER {func.__name__} called from {caller_info.filename}:{caller_info.lineno}")
            
            # Format arguments (excluding self for methods)
            arg_str = []
            for i, arg in enumerate(args):
                if i == 0 and len(args) > 0 and hasattr(args[0], '__class__') and arg.__class__.__name__ == args[0].__class__.__name__:
                    # This is likely 'self' - skip it in the log
                    continue
                    
                # Format the argument
                try:
                    arg_repr = repr(arg)
                    if len(arg_repr) > 50:
                        arg_repr = arg_repr[:50] + "..."
                    arg_str.append(arg_repr)
                except:
                    arg_str.append(f"{type(arg).__name__}")
            
            # Format keyword arguments
            for key, val in kwargs.items():
                try:
                    val_repr = repr(val)
                    if len(val_repr) > 50:
                        val_repr = val_repr[:50] + "..."
                    arg_str.append(f"{key}={val_repr}")
                except:
                    arg_str.append(f"{key}={type(val).__name__}")
                    
            logger.debug(f"  Arguments: {', '.join(arg_str)}")
            
            # Call the function
            result = func(*args, **kwargs)
            
            # Log the result
            try:
                result_repr = repr(result)
                if len(result_repr) > 100:
                    result_repr = result_repr[:100] + "..."
            except:
                result_repr = f"{type(result).__name__}"
                
            logger.debug(f"EXIT {func.__name__} with result: {result_repr}")
            return result
            
        except Exception as e:
            logger.error(f"ERROR in {func.__name__}: {str(e)}")
            logger.debug(traceback.format_exc())
            raise
    
    # Return the appropriate wrapper based on whether the function is async or not
    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
