"""Tests for mapfree.utils.image_list_utils."""

from pathlib import Path

import pytest

from mapfree.utils.image_list_utils import copy_or_link_images


def test_copy_or_link_images_copies_files(tmp_path):
    """copy_or_link_images puts source files into dest_dir."""
    src1 = tmp_path / "a" / "img1.jpg"
    src2 = tmp_path / "b" / "img2.png"
    src1.parent.mkdir(parents=True)
    src2.parent.mkdir(parents=True)
    src1.write_bytes(b"jpeg")
    src2.write_bytes(b"png")
    dest = tmp_path / "out"
    copy_or_link_images([src1, src2], dest)
    assert (dest / "img1.jpg").is_file()
    assert (dest / "img2.png").is_file()
    assert (dest / "img1.jpg").read_bytes() == b"jpeg"


def test_copy_or_link_images_deduplicates_names(tmp_path):
    """Duplicate filenames get unique suffix."""
    a = tmp_path / "img.jpg"
    b = tmp_path / "sub" / "img.jpg"
    b.parent.mkdir(parents=True)
    a.write_bytes(b"1")
    b.write_bytes(b"2")
    dest = tmp_path / "out"
    copy_or_link_images([a, b], dest)
    assert (dest / "img.jpg").is_file()
    assert (dest / "img_1.jpg").is_file()
