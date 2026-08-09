; Example Emacs integration; shows type of expression in region.

(defun mypy-show-region ()
  "Show type of variable at point."
  (interactive)
  (let ((here (region-beginning))
        (there (region-end))
        (filename (buffer-file-name)))
    (let ((hereline (line-number-at-pos here))
          (herecol (save-excursion (goto-char here) (current-column)))
          (thereline (line-number-at-pos there))
          (therecol (save-excursion (goto-char there) (current-column))))
      (shell-command
       (format "cd ~/src/mypy; python3 ./misc/find_type.py %s %s %s %s %s python3 -m mypy -i mypy"
               filename hereline herecol thereline therecol)
       )
      )
    )
  )

; I like to bind this to ^X-t.
(global-set-key "\C-xt" 'mypy-show-region)
