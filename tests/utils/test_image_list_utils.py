"""Tests for mapfree.utils.image_list_utils."""

import pytest

from mapfree.utils.image_list_utils import copy_or_link_images, _link_or_copy_one


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


def test_link_or_copy_one_same_file_no_error(tmp_path):
    """When src and dest are the same file (re-run scenario), no SameFileError."""
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"same")
    _link_or_copy_one(f, f)
    assert f.read_bytes() == b"same"


def test_copy_or_link_images_same_file_in_dest_dir(tmp_path):
    """When dest_dir already contains same file (e.g. re-run), no SameFileError."""
    img = tmp_path / "images" / "DJI_0393.JPG"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"content")
    dest_dir = tmp_path / "project" / "images"
    dest_dir.mkdir(parents=True)
    dest_file = dest_dir / "DJI_0393.JPG"
    dest_file.write_bytes(b"content")
    dest_file.unlink()
    try:
        import os
        os.link(img, dest_file)
    except OSError:
        pytest.skip("hardlink not supported")
    copy_or_link_images([img], dest_dir)
    assert (dest_dir / "DJI_0393.JPG").is_file()
