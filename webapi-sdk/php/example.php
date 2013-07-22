<?php

require('webapi.php');

$api = new WebAPI('demo', '127.0.0.1');

# Get version
printf("Version: %s\n", $api->version());

# Get status
$status = $api->status();

# Get player details
if(in_array('Xharon', $status->players))
{
    $player = $api->player('Xharon', true, true);
    print $player . "\n";
}

# Set time
if($api->time('16:05'))
{
    print "Time set\n";
}

# Get time
$time = $api->time();
print sprintf("Time: %s\n", $time);

# Send global message
if($api->message('Hello server - API'))
{
    print "Message has been sent\n";
}

# Send message to player
if(in_array('Xharon', $status->players))
{
    if($api->message('Hey. How are you?', 'Xharon'))
    {
        print "Message has been sent to Xharon\n";
    }
}

if(in_array('Xharon', $status->players))
{
    if($api->kick('Xharon'))
    {
        print "Xharon has been kicked\n";
    }
}
