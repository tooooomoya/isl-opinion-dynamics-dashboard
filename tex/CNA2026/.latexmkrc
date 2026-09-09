#!/usr/bin/env perl

# LaTeX
$pdflatex = '/Library/TeX/texbin/pdflatex -synctex=1 -halt-on-error -file-line-error %O %S';
$latex = $pdflatex;  # latexmkが$latexを使うときにpdflatexを使わせる
$pdf_mode = 1;       # 1 = pdflatexを使うモード
$max_repeat = 5;

# BibTeX
$bibtex = '/Library/TeX/texbin/bibtex %O %S';
$biber = 'biber --bblencoding=utf8 -u -U --output_safechars %O %S';

# index
$makeindex = 'makeindex %O -o %D %S';

# プレビュー
$pvc_view_file_via_temporary = 0;
if ($^O eq 'linux') {
    $pdf_previewer = "xdg-open %S";
} elsif ($^O eq 'darwin') {
    $pdf_previewer = "open %S";
} else {
    $pdf_previewer = "start %S";
}

# 出力ディレクトリ
$out_dir = 'out';

# クリーン対象の拡張子（スペース区切り）
$clean_full_ext = "aux bbl blg fls fdb_latexmk log synctex.gz out";
