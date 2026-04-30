# Copy every file from ${SRC} into ${DST} but ONLY for files that don't
# already exist on the destination side. Used as a POST_BUILD step to seed
# the dev build's userdata/ from the source repo's userdata/ on first build,
# without trampling subsequent edits made by the running app.
#
# Invoked via: cmake -DSRC=... -DDST=... -P SeedDirIfMissing.cmake

if(NOT IS_DIRECTORY "${SRC}")
    return()
endif()

file(MAKE_DIRECTORY "${DST}")
file(GLOB_RECURSE _files RELATIVE "${SRC}" "${SRC}/*")

foreach(_rel IN LISTS _files)
    set(_target "${DST}/${_rel}")
    if(NOT EXISTS "${_target}")
        get_filename_component(_dir "${_target}" DIRECTORY)
        file(MAKE_DIRECTORY "${_dir}")
        configure_file("${SRC}/${_rel}" "${_target}" COPYONLY)
    endif()
endforeach()
