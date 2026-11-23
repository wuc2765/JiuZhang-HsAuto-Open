"""HsAuto 单文件 bundle 读写工具（.NET 8 apphost + 自定义 header）。

用法:
  python hsbundle.py extract <HsAuto.exe> <out_dir>
  python hsbundle.py repack  <原 HsAuto.exe> <替换文件目录> <out.exe> [名字1 名字2 ...]
  python hsbundle.py info    <HsAuto.exe>

布局: [apphost] [file1..fileN] [header] [table]
entry: offset(8) size(8) compressedSize(8) type(1) pathLen(1) path
header: 8 字节前缀 + FileCount(4) + ... ，长度通过 FileCount 位置反推
apphost 内 8 字节占位符 = header 起点（repack 时改写）

repack 会紧凑重排数据区：只保留仍被引用条目的数据（替换项追加在后），
并同步更新 header 里 deps.json / runtimeconfig.json 的偏移字段。
"""
import struct, sys, os, zlib, hashlib, json

def read_headers(d):
    """反向解析 table，返回 (entries, table_start, header_start, header_len, placeholder_off)"""
    n = len(d)
    entries = []
    end = n
    while end > 0 and len(entries) < 20000:
        found = None
        for L in range(0, 260):
            start = end - 26 - L
            if start < 0:
                break
            t = d[start + 24]
            pl = d[start + 25]
            if pl != L or t > 4 or L == 0:
                continue
            path = d[start + 26:end]
            if len(path) != L:
                continue
            if not all(32 <= b < 127 for b in path):
                continue
            off, size, csize = struct.unpack_from('<qqq', d, start)
            if not (0 <= off < n and 0 <= csize <= size < (1 << 31)):
                continue
            found = (start, off, size, csize, t, path.decode('ascii'))
            break
        if not found:
            break
        entries.append(found)
        end = found[0]
    entries.reverse()
    if not entries:
        raise SystemExit('cannot parse bundle table')
    table_start = entries[0][0]
    count = len(entries)

    # header 长度：FileCount 位于 header_start+8
    header_start = header_len = None
    for H in range(30, 400):
        hs = table_start - H
        if hs < 0:
            break
        try:
            c = struct.unpack_from('<I', d, hs + 8)[0]
        except struct.error:
            continue
        if c == count:
            header_start, header_len = hs, H
            break
    if header_start is None:
        raise SystemExit('cannot locate header (FileCount mismatch)')

    # apphost 内占位符
    min_off = min(e[1] for e in entries)
    target = struct.pack('<q', header_start)
    placeholder = None
    i = d.find(target, 0, min_off)
    while i != -1:
        placeholder = i
        break
    if placeholder is None:
        # 可能是 4 字节占位
        raise SystemExit('cannot locate BundleHeaderOffset placeholder')

    return entries, table_start, header_start, header_len, placeholder


def cmd_info(path):
    d = open(path, 'rb').read()
    entries, ts, hs, hl, ph = read_headers(d)
    print('file       : %s (%d bytes)' % (path, len(d)))
    print('entries    : %d' % len(entries))
    print('data range : %#x .. %#x' % (min(e[1] for e in entries), max(e[1] + (e[3] or e[2]) for e in entries)))
    print('header     : %#x (len %d)' % (hs, hl))
    print('table      : %#x' % ts)
    print('placeholder: %#x' % ph)
    for e in entries:
        if e[5] in ('HsAuto.dll', 'HsAuto.Core.dll', 'HsAuto.deps.json', 'HsAuto.runtimeconfig.json', 'hdt_v3.dll'):
            print('  %-32s off=%#x size=%d csize=%d type=%d' % (e[5], e[1], e[2], e[3], e[4]))


def cmd_extract(path, out_dir):
    d = open(path, 'rb').read()
    entries, ts, hs, hl, ph = read_headers(d)
    os.makedirs(out_dir, exist_ok=True)
    for _, off, size, csize, t, name in entries:
        raw = d[off:off + (csize or size)]
        if csize:
            raw = zlib.decompressobj(-15).decompress(raw)
        dst = os.path.join(out_dir, name.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(raw)
    print('extracted %d files to %s' % (len(entries), out_dir))


def cmd_repack(orig, patch_dir, out, names):
    d = open(orig, 'rb').read()
    entries, ts, hs, hl, ph = read_headers(d)
    data_start = min(e[1] for e in entries)

    # header(version 6) 布局：
    #   u64 version | u32 file_count | u8 id_len | id
    #   | q deps_off | q deps_size | q runtimeconfig_off | q runtimeconfig_size | q flags
    header = bytearray(d[hs:hs + hl])
    id_len = header[12]
    deps_pos = 13 + id_len
    if deps_pos + 40 != hl:
        raise SystemExit('unexpected header layout: len=%d id_len=%d' % (hl, id_len))
    hdeps_off, hdeps_size, hrt_off, hrt_size = struct.unpack_from('<qqqq', header, deps_pos)
    deps_entry = next((x for x in entries if x[5] == 'HsAuto.deps.json'), None)
    rt_entry = next((x for x in entries if x[5] == 'HsAuto.runtimeconfig.json'), None)
    if deps_entry and (hdeps_off != deps_entry[1] or hdeps_size != deps_entry[2]):
        raise SystemExit('header deps.json fields mismatch entry')
    if rt_entry and (hrt_off != rt_entry[1] or hrt_size != rt_entry[2]):
        raise SystemExit('header runtimeconfig fields mismatch entry')

    replaced_names = set(names)
    entries = [list(x) for x in entries]
    by_name = {x[5]: x for x in entries}

    # 紧凑排布：只复制仍被引用条目的数据，旧条目数据不再留在文件里。
    buf = bytearray(d[:data_start])
    copied = {}
    for x in sorted((x for x in entries if x[5] not in replaced_names), key=lambda x: x[1]):
        key = (x[1], x[2], x[3])
        if key in copied:
            x[1] = copied[key]
            continue
        raw = d[x[1]:x[1] + (x[3] or x[2])]
        x[1] = len(buf)
        copied[key] = x[1]
        buf.extend(raw)

    for name in names:
        src = os.path.join(patch_dir, name)
        if not os.path.exists(src):
            raise SystemExit('missing replacement: ' + src)
        x = by_name.get(name)
        if x is None:
            raise SystemExit('entry not found in bundle: ' + name)
        blob = open(src, 'rb').read()
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        packed = comp.compress(blob) + comp.flush()
        x[1], x[2], x[3] = len(buf), len(blob), len(packed)
        buf.extend(packed)
        print('  replace %-20s %9d -> %8d @ %#x' % (name, len(blob), len(packed), x[1]))

    # header 里 deps.json / runtimeconfig.json 的偏移跟随条目移动
    if deps_entry:
        x = by_name['HsAuto.deps.json']
        struct.pack_into('<qq', header, deps_pos, x[1], x[2])
    if rt_entry:
        x = by_name['HsAuto.runtimeconfig.json']
        struct.pack_into('<qq', header, deps_pos + 16, x[1], x[2])

    new_header_start = len(buf)
    buf.extend(header)
    for st, off, size, csize, t, name in entries:
        buf.extend(struct.pack('<qqq', off, size, csize))
        buf.append(t)
        p = name.encode('utf-8')
        if len(p) >= 256:
            raise SystemExit('path too long: ' + name)
        buf.append(len(p))
        buf.extend(p)
    struct.pack_into('<q', buf, ph, new_header_start)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    open(out, 'wb').write(bytes(buf))
    print('  header %#x -> %#x, eof %#x, size %d' % (hs, new_header_start, len(buf), len(buf)))
    verify(out, orig, entries, replaced_names, patch_dir)


def verify(path, orig_path, expected_entries, replaced_names, patch_dir=None):
    d = open(path, 'rb').read()
    orig = open(orig_path, 'rb').read()
    entries, ts, hs, hl, ph = read_headers(d)
    oentries, _ots, _ohs, _ohl, _oph = read_headers(orig)
    assert len(entries) == len(expected_entries), 'entry count changed'
    assert ts + sum(26 + len(e[5]) for e in entries) == len(d), 'table does not end at EOF'
    omap = {e[5]: e for e in oentries}
    rmap = {e[5]: e for e in entries}
    assert set(rmap) == set(omap), 'entry names changed'

    for e in entries:
        assert 0 <= e[1] and e[1] + (e[3] or e[2]) <= hs, 'entry out of data range: ' + e[5]

    # 未替换条目必须与原包逐字节一致
    for e in entries:
        if e[5] in replaced_names:
            continue
        raw = d[e[1]:e[1] + (e[3] or e[2])]
        if e[3]:
            raw = zlib.decompressobj(-15).decompress(raw)
        o = omap[e[5]]
        oraw = orig[o[1]:o[1] + (o[3] or o[2])]
        if o[3]:
            oraw = zlib.decompressobj(-15).decompress(oraw)
        assert hashlib.sha256(raw).digest() == hashlib.sha256(oraw).digest(), 'content changed: ' + e[5]

    # header 里 deps.json / runtimeconfig.json 的偏移必须指向正确条目
    header = d[hs:hs + hl]
    p = 13 + header[12]
    hd, hds, hr, hrs = struct.unpack_from('<qqqq', header, p)
    assert hd == rmap['HsAuto.deps.json'][1] and hds == rmap['HsAuto.deps.json'][2], 'bad deps.json header offset'
    assert hr == rmap['HsAuto.runtimeconfig.json'][1] and hrs == rmap['HsAuto.runtimeconfig.json'][2], 'bad runtimeconfig header offset'

    for name in replaced_names:
        e = rmap[name]
        raw = d[e[1]:e[1] + (e[3] or e[2])]
        if e[3]:
            raw = zlib.decompressobj(-15).decompress(raw)
        assert len(raw) == e[2], 'size mismatch: ' + name
        if patch_dir:
            src = open(os.path.join(patch_dir, name), 'rb').read()
            assert hashlib.sha256(raw).digest() == hashlib.sha256(src).digest(), 'replacement content mismatch: ' + name
        print('  verify %-20s ok sha256=%s' % (name, hashlib.sha256(raw).hexdigest()[:16]))
    print('  self-check passed (%d entries, data range %#x .. %#x)' % (len(entries), min(e[1] for e in entries), hs))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == 'info':
        cmd_info(sys.argv[2])
    elif cmd == 'extract':
        cmd_extract(sys.argv[2], sys.argv[3])
    elif cmd == 'repack':
        orig, patch_dir, out = sys.argv[2], sys.argv[3], sys.argv[4]
        names = sys.argv[5:] or ['HsAuto.dll', 'HsAuto.Core.dll']
        cmd_repack(orig, patch_dir, out, names)
    else:
        print(__doc__)
        sys.exit(2)
