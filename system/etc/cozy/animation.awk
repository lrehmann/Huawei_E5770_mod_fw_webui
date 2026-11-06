# Replace complete frame payloads, retaining the vendor's geometry and timing.
BEGIN {
    while ((getline line < boot)>0) boothex=boothex line
    while ((getline line < bye)>0) byehex=byehex line
}
function frame(hex, count, i, j) {
    print "<bitmap>"
    for (j=0;j<count;j++) {
        print "<frame>"
        for (i=1;i<=length(hex);i+=2) {
            printf "0x%s,", substr(hex,i,2)
            if ((i+1)%32==0) printf "\n"
        }
        print "\n</frame>"
    }
    print "</bitmap>"
}
/<welcome>/ || /<fast_power_up>/ { target=1 }
/<fast_power_down>/ || /<ani_power_off>/ { target=2 }
target && /<bmp_total>/ { n=$0; sub(/.*<bmp_total>/,"",n); sub(/<.*/,"",n); count=n+0 }
target && /<bitmap>/ { frame(target==1 ? boothex : byehex, count); skip=1 }
skip { if (/<\/bitmap>/) skip=0; next }
{ print }
/<\/welcome>/ || /<\/fast_power_up>/ || /<\/fast_power_down>/ || /<\/ani_power_off>/ { target=0; count=1 }
