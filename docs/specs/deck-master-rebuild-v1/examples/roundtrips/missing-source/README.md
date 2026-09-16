# 缺原文导入往返

输入：旧目录有正文、已保存extract与Logo等媒体；原PDF已经不可达。inspect只读列出缺口。import在新project中保存可读字节，source.original_sha256为null或缺省，原URI作为历史线索保留。

project是合成的新项目布局，已保存文件均有真实字节hash。document-hash-omitted.json与project中null版都应通过schema；invalid-zero-hash.json必须拒绝。源hash未知不允许放松存储Ref.hash。

预期动作：view可读取现有正文/Logo，不等待原PDF复活；基于extract继续合理讨论可行，但必须说明只能核对保存文本。需要原PDF中的图表或精确来源核查时，针对该动作提示缺源。后来指定candidate.pdf时先测量新字节，仅将其记为本次核实的候选来源，不能因为文件名相同追认它就是旧原件。原记录/媒体/失败状态不改。

这些是格式与状态范例，未执行实际legacy命令。
