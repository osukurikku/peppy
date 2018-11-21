<?php
        $plainPassword = 'kotriks_fokabot_production_dev';
        $options = ['cost' => 9, 'salt' => base64_decode(base64_encode(mcrypt_create_iv(22, MCRYPT_DEV_URANDOM)))];
        $md5Password = crypt(md5($plainPassword), '$2y$'.$options['salt']);
	echo $md5Password."\n".base64_encode($options['salt'])."\n";

?>
