_shipami_completion() {
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _SHIPAMI_COMPLETE=complete $1 ) )
    return 0
}

complete -F _shipami_completion -o default shipami;
