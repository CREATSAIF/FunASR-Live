#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR Live - 实时语音识别工具
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="funasr-live",
    version="1.0.0",
    author="CREATSAIF",
    author_email="",
    description="实时语音识别工具，支持快捷键触发、连续识别、剪贴板输出",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CREATSAIF/FunASR-Live",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
    ],
    python_requires=">=3.9",
    install_requires=[
        "funasr>=1.0.0",
        "torch>=2.0.0",
        "torchaudio>=2.0.0",
        "sounddevice>=0.4.6",
        "numpy>=1.21.0",
        "PyYAML>=6.0",
        "pynput>=1.7.6",
        "pyperclip>=1.8.2",
        "PyQt5>=5.15.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "websockets>=11.0",
    ],
    entry_points={
        "console_scripts": [
            "funasr-live=funasr_live:main",
            "funasr-realtime=funasr_realtime:main",
        ],
        "gui_scripts": [
            "funasr-gui=realtime_gui:main",
            "funasr-settings=settings_gui:main",
        ],
    },
)
