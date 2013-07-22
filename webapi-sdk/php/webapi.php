<?php

class UnauthorizedException extends Exception {
}


class InvalidResourceException extends Exception
{
}


class InvalidPlayerException extends Exception
{
}


class InvalidTimeException extends Exception
{
}


class InvalidMethodException extends Exception
{
}


class Status
{
    public $players;
    public $player_limit;
    public $seed;

    public function __construct($result)
    {
        $this->players = $result['players'];
        $this->player_limit = $result['player-limit'];
        $this->seed = $result['seed'];
    }

    public function __toString()
    {
        return sprintf('Status {players=[%s], player_limit=%s, seed=%s}',
                        implode(', ', $this->players), $this->player_limit,
                        $this->seed);
    }
}


class Player
{
    public $has_equipment = false;
    public $has_skills = false;
    public $name;
    public $position;
    public $class_type;
    public $specialization;
    public $level;
    public $power_level;
    public $equipment = array();
    public $skills = array();

    public function __construct($result)
    {
        $this->has_equipment = isset($result['equipment']);
        $this->has_skills = isset($result['skills']);
        $this->name = $result['name'];
        $this->position = array('x' => $result['position']['x'],
                                'y' => $result['position']['y'],
                                'z' => $result['position']['z']);
        $this->class_type = $result['class'];
        $this->specialization = $result['specialization'];
        $this->level = $result['level'];
        $this->power_level = $result['power-level'];
        if($this->has_equipment)
        {
            $this->parse_equipment($result['equipment']);
        }
        if($this->has_skills)
        {
            $this->parse_skills($result['skills']);
        }
    }

    private function parse_equipment($result)
    {
        foreach($result as $item)
        {
            $this->equipment[] = new Item($item);
        }
    }

    private function parse_skills($result)
    {
        $this->skills['pet_master'] = $result['pet-master'];
        $this->skills['riding'] = $result['riding'];
        $this->skills['climbing'] = $result['climbing'];
        $this->skills['hang_gliding'] = $result['hang-gliding'];
        $this->skills['swimming'] = $result['swimming'];
        $this->skills['sailing'] = $result['sailing'];
        $this->skills['class_skill_1'] = $result['class-skill-1'];
        $this->skills['class_skill_2'] = $result['class-skill-2'];
        $this->skills['class_skill_3'] = $result['class-skill-3'];
    }

    public function __toString()
    {
        $string = sprintf('Player {name=%s, ...}', $this->name);
        if($this->has_equipment)
        {
            $string .= ' [Has_Equipment]';
        }
        if($this->has_skills)
        {
            $string .= ' [Has_Skills]';
        }
        return $string;
    }
}


class Item
{
    public $type;
    public $sub_type;
    public $modifier;
    public $minus_modifier;
    public $rarity;
    public $material;
    public $flags;
    public $level;
    public $power_level;
    public $upgrades = array();

    public function __construct($result)
    {
        $this->type = $result['type'];
        $this->sub_type = $result['sub-type'];
        $this->modifier = $result['modifier'];
        $this->minus_modifier = $result['minus-modifier'];
        $this->rarity = $result['rarity'];
        $this->material = $result['material'];
        $this->flags = $result['flags'];
        $this->level = $result['level'];
        $this->power_level = $result['power-level'];
        foreach($result['upgrades'] as $upgrade)
        {
            $this->upgrades[] = new ItemUpgrade($upgrade);
        }
    }

    public function __toString()
    {
        $string = sprintf('Item {type=%s, sub_type=%s, rarity=%s, ...}',
                            $this->type, $this->sub_type, $this->rarity);
        $string .= sprintf(" [%s upgrades]",count($this->upgrades));
        return $string;
    }
}


class ItemUpgrade
{
    public $x;
    public $y;
    public $z;
    public $material;
    public $level;

    public function __construct($result)
    {
        $this->x = $result['x'];
        $this->y = $result['y'];
        $this->z = $result['z'];
        $this->material = $result['material'];
        $this->level = $result['level'];
    }

    public function __toString()
    {
        return sprintf('ItemUpgrade {x=%s, y=%s, z=%s, material=%s, level=%s}',
                        $this->x, $this->y, $this->z, $this->material,
                        $this->level);
    }
}


class WebAPI
{
    const URL_FORMAT = 'http://%s:%s/%s';

    private $host;
    private $port;
    private $key;

    public function __construct($key, $host, $port = 12350)
    {
        $this->key = $key;
        $this->host = $host;
        $this->port = $port;

        if(!extension_loaded('cURL'))
        {
            throw new Exception('WebAPI requires PHP cURL extension to work');
        }
    }

    private function generateUrl($endpoint, $secure, $queryParams = null)
    {
        $url = sprintf(WebAPI::URL_FORMAT, $this->host, $this->port, $endpoint);

        if($secure)
        {
            $url .= sprintf("?key=%s", urlencode($this->key));
        }

        if(!is_null($queryParams) && is_array($queryParams))
        {
            $url .= ($secure ? "&" : "?");
            $url .= http_build_query($queryParams);
        }

        return $url;
    }

    private function send($endpoint = '', $data = null, $secure = true, $queryParams = null)
    {
        $url = $this->generateUrl($endpoint, $secure, $queryParams);
        $handle = curl_init($url);
        curl_setopt($handle, CURLOPT_PORT, $this->port);
        curl_setopt($handle, CURLOPT_HEADER, false);
        curl_setopt($handle, CURLOPT_RETURNTRANSFER, true);
        if(!is_null($data))
        {
            curl_setopt($handle, CURLOPT_POST, true);
            curl_setopt($handle, CURLOPT_POSTFIELDS, $data);
        }       
        $result = curl_exec($handle);
        curl_close($handle);
        return $this->parse($result);
    }

    private function handleError($result)
    {
        $errorCode = $result['error'];
        switch($errorCode)
        {
            case -1:
                throw new UnauthorizedException();
            case -2:
                throw new InvalidResourceException();
            case -3:
                throw new InvalidPlayerException();
            case -4:
                throw new InvalidTimeException();
            case -5:
                throw new InvalidMethodException();
        }
    }

    private function parse($data)
    {
        $result = json_decode($data, true);
        if(isset($result['error']))
        {
            $this->handleError($result);
        }
        return $result;
    }

    public function version()
    {
        $result = $this->send('', null, false);
        return $result['version'];
    }

    public function status()
    {
        $result = $this->send('status');
        return new Status($result);
    }

    public function player($name, $includeEquipment = false, $includeSkills = false)
    {
        $inclusion = array();
        if($includeEquipment)
        {
            $inclusion[] = 'equipment';
        }
        if($includeSkills)
        {
            $inclusion[] = 'skills';
        }
        $params = null;
        if(count($inclusion) > 0)
        {
            $params = array('include', implode(',', $inclusion));
        }
        $result = $this->send(sprintf('player/%s', $name), null, true, $params);
        return new Player($result['player']);
    }

    public function kick($name)
    {
        $result = $this->send(sprintf('kick/%s', $name));
        return isset($result['success']);
    }

    public function time($value = null)
    {
        if(is_null($value)) {
            $result = $this->send('time');
            return $result['time'];
        }
        $parsed = date_parse_from_format('H:i', $value);
        if($parsed['error_count'] != 0) {
            throw new InvalidTimeException();
        }
        $result = $this->send(sprintf('time/%s', $value));
        return isset($result['success']);
    }

    public function message($message, $receiver = null)
    {
        $endpoint = 'message/';
        if(!is_null($receiver))
        {
            $endpoint .= sprintf('%s/', $receiver);
        }
        $result = $this->send($endpoint, $message);
        return isset($result['success']);
    }
}
