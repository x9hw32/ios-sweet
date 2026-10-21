"""Bounded flattened device tree reader; addresses retain their DT cell widths."""
from dataclasses import dataclass, field
import struct


@dataclass
class Node:
    name: str
    path: str
    parent: 'Node | None' = None
    props: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def strings(self, key):
        return self.props.get(key, b'').rstrip(b'\0').decode(errors='replace').split('\0')

    def cell_count(self, key, default):
        value = self.props.get(key)
        if value is None:
            return default
        if len(value) != 4:
            raise ValueError(f'{self.path}: invalid {key}')
        result, = struct.unpack('>I', value)
        if result > 4:
            raise ValueError(f'{self.path}: unsupported {key}={result}')
        return result

    def ranges(self, key='reg'):
        """Decode reg in the immediate parent's address space (no translation)."""
        parent = self.parent
        ac = parent.cell_count('#address-cells', 2) if parent else 2
        sc = parent.cell_count('#size-cells', 1) if parent else 1
        width = 4 * (ac + sc)
        value = self.props.get(key, b'')
        if not width or len(value) % width:
            raise ValueError(f'{self.path}: malformed {key}')
        return [(int.from_bytes(value[i:i+4*ac], 'big'),
                 int.from_bytes(value[i+4*ac:i+width], 'big'))
                for i in range(0, len(value), width)]


def parse(data):
    if len(data) < 40:
        raise ValueError('Truncated FDT header')
    magic, total, off, strings, reserve, version, last, cpu, ns, nt = struct.unpack_from('>10I', data)
    if magic != 0xd00dfeed or total > len(data) or version < 17:
        raise ValueError('Invalid FDT header')
    if strings + ns > total or off + nt > total or reserve >= total:
        raise ValueError('FDT block outside file')
    def cstr(start, limit):
        end = data.find(b'\0', start, limit)
        if end < 0:
            raise ValueError('Unterminated FDT string')
        return data[start:end].decode(), end + 1
    stack = []
    nodes = {}
    end = off + nt
    done = False
    while off + 4 <= end:
        token, = struct.unpack_from('>I', data, off)
        off += 4
        if token == 1:
            name, off = cstr(off, end)
            off = (off + 3) & ~3
            parent = stack[-1] if stack else None
            path = (parent.path.rstrip('/') + '/' + name) if parent else '/'
            node = Node(name, path, parent)
            if path in nodes:
                raise ValueError('Duplicate FDT node')
            if parent:
                parent.children.append(node)
            nodes[path] = node
            stack.append(node)
        elif token == 2:
            if not stack:
                raise ValueError('Unbalanced FDT node')
            stack.pop()
        elif token == 3:
            if not stack or off + 8 > end:
                raise ValueError('Invalid FDT property')
            size, nameoff = struct.unpack_from('>II', data, off)
            off += 8
            if off + size > end or nameoff >= ns:
                raise ValueError('FDT property outside block')
            key, _ = cstr(strings + nameoff, strings + ns)
            stack[-1].props[key] = data[off:off + size]
            off = (off + size + 3) & ~3
        elif token == 9:
            if stack:
                raise ValueError('Unclosed FDT nodes')
            done = True
            break
        elif token != 4:
            raise ValueError(f'Unexpected FDT token {token}')
    if not done or '/' not in nodes:
        raise ValueError('Missing FDT end')
    reservations = []
    while reserve + 16 <= total:
        base, size = struct.unpack_from('>QQ', data, reserve)
        reserve += 16
        if not base and not size:
            return nodes, reservations
        reservations.append((base, size))
    raise ValueError('Unterminated FDT reservations')
