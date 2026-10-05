import io

p = 'build_site.py'
s = io.open(p, encoding='utf-8').read()
css = io.open('_new_style.css', encoding='utf-8').read().rstrip('\n')

head = 'STYLE = """' + chr(92) + '\n'
start = s.index(head)
end = s.index('\n"""\n', start) + len('\n"""\n')
new = head + css + '\n"""\n'
s = s[:start] + new + s[end:]
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('STYLE 已替换：旧', end - start, '字符 -> 新', len(new), '字符')
