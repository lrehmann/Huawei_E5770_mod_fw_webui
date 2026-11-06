# Validate data; never source user settings as shell code. Exit nonzero on error.
BEGIN { FS="="; bad=0; total=0 }
{
    total++
    if (index($0, "=") == 0) { bad=1; next }
    key=$1; value=substr($0, length(key)+2)
    if (seen[key]++) bad=1
    if (key=="version") { if (value!="1") bad=1 }
    else if (key=="theme") { if (value!="cat" && value!="cloud" && value!="sprout") bad=1 }
    else if (key=="label") { if (length(value)<1 || length(value)>16 || value ~ /[^A-Z0-9 ._-]/) bad=1 }
    else if (key=="message") { if (length(value)<1 || length(value)>18 || value ~ /[^A-Z0-9 !?.'_-]/) bad=1 }
    else if (key=="dim_seconds") { if (value !~ /^[0-9]+$/ || value+0<1 || value+0>60) bad=1; dim=value+0 }
    else if (key=="sleep_seconds") { if (value !~ /^[0-9]+$/ || value+0<1 || value+0>300) bad=1; sleep=value+0 }
    else if (key=="poll_seconds") { if (value!="5" && value!="10" && value!="30" && value!="60") bad=1 }
    else if (key=="boot64") { if (length(value)!=2048 || value ~ /[^0-9a-f]/) bad=1 }
    else if (key=="boot128") { if (length(value)!=4096 || value ~ /[^0-9a-f]/) bad=1 }
    else bad=1
}
END {
    if (total!=9 || sleep<dim) bad=1
    for (i=1;i<=9;i++) {
        split("version theme label message dim_seconds sleep_seconds poll_seconds boot64 boot128", keys, " ")
        if (seen[keys[i]]!=1) bad=1
    }
    exit bad
}
